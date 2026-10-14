#!/usr/bin/env python3
"""
evaluator.py — Contrastive Speech Delivery Evaluator
=====================================================
A measured, speaker-normalized audio evaluation pipeline for comparing
candidate speech delivery against a reference speech baseline.

Features
--------
1. Input validation & audio sanity checks (duration, silence, decode).
2. Word-level wav2vec2 CTC alignment with validated caching.
3. Speaker-agnostic acoustic feature extraction:
   - Pitch: F0 via pYIN, converted to semitones with unvoiced NaN masking,
     median-centered for speaker register invariance without compressing variance.
   - Energy: RMS and dB scale with gain compensation via speech-active medians.
   - Pacing: Global WPM, articulation rate (excluding pauses), and local window WPM.
4. Word-boundary pause analysis:
   - Distinguishes natural sentence-boundary pauses from mid-phrase awkward silences.
5. Text-constrained piecewise correspondence using matching word boundaries.
6. Temporal grounding with merged overlapping flaw regions and causal explanations.
7. Rubric scoring (0–100) with category subscores and transparent deduction tracking.
8. Safe JSON serialization (handles all NumPy floats, NaNs, and infinities).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
import warnings
import hashlib
from uuid import uuid4
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import librosa
import numpy as np
from scipy.ndimage import uniform_filter1d

import speech_runtime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("evaluator")

# ═══════════════════════════════════════════════════════════════════════════════
# Central Configuration Dataclass
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class EvaluatorConfig:
    """
    Central configurable parameters for the speech evaluation pipeline.
    All thresholds are documented with units, rationale, and bounds.
    """

    # Audio preprocessing
    sr: int = 16_000  # Standard sample rate (Hz)
    hop_length: int = 256  # Hop size for STFT/features (~16 ms @ 16kHz)
    min_duration_sec: float = 0.5  # Minimum audio length to evaluate (seconds)
    max_duration_sec: float = 180.0  # Bound CPU alignment memory for local use
    min_speech_rms: float = 1e-4  # Minimum RMS to reject completely silent files
    cache_dir: Optional[str] = None
    cpu_threads: int = 4
    enable_clarity: bool = True
    asr_model: str = "base.en"
    min_alignment_coverage: float = (
        0.90  # Reject alignments missing most transcript tokens
    )

    # Pitch (F0) extraction
    fmin_hz: float = 65.0  # Minimum pitch frequency (Hz, typical human floor)
    fmax_hz: float = 600.0  # Maximum pitch frequency (Hz, typical human ceiling)
    min_voiced_ratio: float = (
        0.15  # Minimum voiced frames required to analyze intonation
    )
    min_voiced_frames: int = 10  # Absolute minimum voiced frames for pitch statistics

    # Monotone detection
    # Candidate pitch standard deviation < (baseline_std * monotone_std_ratio) triggers monotone
    monotone_std_ratio: float = (
        0.40  # Relative pitch variation threshold (40% of baseline)
    )
    min_baseline_semitone_std: float = (
        0.75  # Baseline must have at least 0.75 semitones std dev
    )
    window_sec: float = 2.0  # Sliding window duration for local contour check (sec)
    window_step_sec: float = 1.0  # Step size for sliding window (sec)

    # Speaking rate (WPM)
    # Thresholds are relative ratios to baseline speaking rate
    rushed_wpm_ratio: float = 1.30  # >130% of baseline WPM considered rushed
    slow_wpm_ratio: float = 0.70  # <70% of baseline WPM considered slow

    # Pause detection
    pause_min_sec: float = (
        0.4  # Minimum gap between words to count as a pause (seconds)
    )
    awkward_pause_sec: float = (
        1.5  # Gap duration that may represent hesitation mid-phrase
    )
    sentence_boundary_max_sec: float = (
        2.5  # Acceptable pause at natural punctuation ends
    )

    # Energy / Loudness comparison
    # Compares relative local dB drop between speaker-normalized energy levels
    energy_dip_db_threshold: float = 12.0  # dB drop relative to speaker active median
    speech_active_db_floor: float = -45.0  # Frames below this dB are treated as silence

    # Deductions per flaw type (base points deducted from 100)
    deduction_weights: Dict[str, int] = field(
        default_factory=lambda: {
            "monotone_delivery": 6,
            "rushed_pacing": 6,
            "slow_pacing": 5,
            "awkward_pause": 5,
            "low_energy": 4,
        }
    )

    # Smoothing window for DTW matching (frames)
    smooth_win_frames: int = 9


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class WordTimestamp:
    """Word-level alignment timestamp."""

    word: str
    start: float
    end: float
    confidence: Optional[float] = None


@dataclass
class EvidenceData:
    """Structured causal evidence supporting a detected flaw."""

    baseline_value: Optional[float] = None
    participant_value: Optional[float] = None
    absolute_deviation: Optional[float] = None
    difference_percent: Optional[float] = None
    normalized_deviation: Optional[float] = None
    units: str = ""
    measurement_name: str = ""
    source: str = "measured"
    additional: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FlawRegion:
    """A temporally-grounded delivery flaw with causal rationale."""

    flaw_type: str
    start_time: float
    end_time: float
    severity: int  # Integer 1 (mild) to 5 (severe)
    confidence: Optional[float]  # None until independently calibrated
    description: str
    causal_explanation: str
    evidence: EvidenceData
    measured_value: Optional[float] = None
    threshold: Optional[float] = None
    reference_value: Optional[float] = None
    transcript_excerpt: Optional[str] = None
    recommendation: str = ""


@dataclass
class SpeechRateMetrics:
    """Detailed speaking rate and articulation measurements."""

    total_words: int
    duration_sec: float
    spoken_duration_sec: float
    speech_active_sec: float
    global_wpm: float
    articulation_wpm: float
    pauses: List[Dict[str, Any]] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Model Cache & Transcription Helpers
# ═══════════════════════════════════════════════════════════════════════════════

_ALIGN_MODEL_CACHE: Dict[Tuple[str, str], Tuple[Any, Any]] = {}
_ASR_MODEL_CACHE: Dict[Tuple[str, str, str], Any] = {}


class AlignmentError(RuntimeError):
    """Raised when genuine word-level alignment cannot be produced safely."""


def normalize_token(token: str) -> str:
    """Normalize a transcript token for matching; keeps letters and digits only."""
    return "".join(re.findall(r"[\w']+", token.casefold(), flags=re.UNICODE)).strip("'")


def _transcript_tokens(text: str) -> List[str]:
    return [normalize_token(token) for token in text.split() if normalize_token(token)]


def _validate_aligned_words(
    words: List[WordTimestamp],
    duration: float,
    transcript_text: str,
    config: EvaluatorConfig,
) -> List[WordTimestamp]:
    """Validate returned aligner timestamps and reject incomplete/untrustworthy results."""
    if not words:
        raise AlignmentError(
            "The aligner returned no valid word timestamps; refusing to synthesize timestamps."
        )
    valid: List[WordTimestamp] = []
    previous_start = -1.0
    for item in words:
        try:
            start, end = float(item.start), float(item.end)
        except (TypeError, ValueError) as exc:
            raise AlignmentError("Alignment contains non-numeric timestamps.") from exc
        if not (math.isfinite(start) and math.isfinite(end)):
            raise AlignmentError("Alignment contains non-finite timestamps.")
        if not item.word or not item.word.strip():
            continue
        # Do not silently clamp real errors into apparently plausible timestamps.
        if start < -0.02 or end > duration + 0.02 or end <= start:
            raise AlignmentError(
                f"Invalid word interval for {item.word!r}: {start:.3f}-{end:.3f}s "
                f"(audio duration {duration:.3f}s)."
            )
        if start + 1e-3 < previous_start:
            raise AlignmentError("Alignment timestamps are not in chronological order.")
        # Clamp only the tiny floating-point tolerance accepted above, then validate
        # again; an interval just beyond EOF must not become zero/negative-length data.
        start = min(duration, max(0.0, start))
        end = min(duration, max(0.0, end))
        if end <= start:
            raise AlignmentError(
                f"Word interval for {item.word!r} is empty after bounds checking."
            )
        valid.append(
            WordTimestamp(
                item.word.strip(), round(start, 4), round(end, 4), item.confidence
            )
        )
        previous_start = start

    expected = _transcript_tokens(transcript_text)
    aligned = _transcript_tokens(" ".join(w.word for w in valid))
    if not expected or not aligned:
        raise AlignmentError(
            "Transcript or aligned output contains no matchable words."
        )
    # Coverage is intentionally tolerant of punctuation/tokenization differences, but
    # stops partial alignments from producing confidently grounded reports.
    from collections import Counter

    exp_count, got_count = Counter(expected), Counter(aligned)
    matched = sum(min(count, got_count[token]) for token, count in exp_count.items())
    coverage = matched / max(1, len(expected))
    if coverage < config.min_alignment_coverage:
        raise AlignmentError(
            f"Alignment coverage too low ({coverage:.0%}; requires "
            f"{config.min_alignment_coverage:.0%}). Check transcript language/text and retry."
        )
    return valid


def transcribe_audio(
    audio_path: str,
    device: str = "cpu",
    model_name: str = "base.en",
    language: str = "en",
    cache_dir=None,
    cpu_threads=4,
) -> str:
    """Local Faster-Whisper transcription with VAD and explicit CPU int8 mode."""
    return speech_runtime.transcribe(
        audio_path,
        device=device,
        model_name=model_name,
        language=language,
        cache_dir=cache_dir,
        cpu_threads=cpu_threads,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1: Input Validation & Forced Alignment
# ═══════════════════════════════════════════════════════════════════════════════


def validate_audio_file(
    audio_path: str, config: EvaluatorConfig
) -> Tuple[np.ndarray, int, float]:
    """
    Validates audio file existence, decodability, duration bounds, and signal presence.
    Returns (audio_array, sample_rate, duration_seconds).
    """
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Audio file is empty (0 bytes): {audio_path}")

    try:
        y, sr = librosa.load(str(path), sr=config.sr, mono=True)
    except Exception as exc:
        raise ValueError(f"Failed to decode audio file {audio_path}: {exc}") from exc

    duration = float(librosa.get_duration(y=y, sr=sr))
    if duration < config.min_duration_sec:
        raise ValueError(
            f"Audio duration ({duration:.2f}s) is below minimum threshold ({config.min_duration_sec}s)."
        )
    if duration > config.max_duration_sec:
        raise ValueError(
            f"Audio duration ({duration:.2f}s) exceeds maximum limit ({config.max_duration_sec}s)."
        )

    # Check for silent audio
    rms = float(np.sqrt(np.mean(y**2)))
    if rms < config.min_speech_rms:
        raise ValueError(
            f"Audio file appears completely silent or below signal threshold (RMS={rms:.2e} < {config.min_speech_rms:.2e})."
        )

    return y, sr, duration


def align_audio(
    audio_path: str,
    transcript_text: str,
    device: str = "cpu",
    language: str = "en",
    config=None,
) -> List[WordTimestamp]:
    """Align every confirmed English word using wav2vec2 CTC; fail on poor evidence."""
    config = config or EvaluatorConfig()
    if language != "en":
        raise AlignmentError(
            "The bundled alignment model supports English. Choose English speech."
        )
    y, sr, duration = validate_audio_file(audio_path, config)
    try:
        cache_root = (
            Path(config.cache_dir or Path(__file__).parent / "model-artifacts")
            / "alignments"
        )
        cache_root.mkdir(parents=True, exist_ok=True)
        fingerprint = hashlib.sha256(
            Path(audio_path).read_bytes()
            + transcript_text.encode()
            + b"wav2vec2-base-960h-v3"
        ).hexdigest()
        cached = cache_root / (fingerprint + ".json")
        if cached.exists():
            try:
                return _validate_aligned_words(
                    [WordTimestamp(**w) for w in json.loads(cached.read_text())],
                    duration,
                    transcript_text,
                    config,
                )
            except (ValueError, TypeError, AlignmentError):
                cached.unlink(missing_ok=True)
        raw = speech_runtime.align_words(
            y,
            transcript_text,
            sr,
            device,
            cache_dir=config.cache_dir,
            cpu_threads=config.cpu_threads,
        )
        words = _validate_aligned_words(
            [WordTimestamp(**w) for w in raw], duration, transcript_text, config
        )
        confidences = [w.confidence for w in words if w.confidence is not None]
        if (
            not confidences
            or np.mean(confidences) < 0.12
            or np.mean(np.array(confidences) < 0.025) > 0.35
        ):
            raise AlignmentError(
                "Low alignment confidence. Verify the transcript against the actual recording."
            )
        temporary = cached.with_suffix("." + uuid4().hex + ".tmp")
        temporary.write_text(json.dumps([asdict(w) for w in words]), encoding="utf-8")
        temporary.replace(cached)
        return words
    except AlignmentError:
        raise
    except Exception as exc:
        raise AlignmentError(
            "Local word alignment failed. Check model files, audio and English transcript."
        ) from exc


def _pause_boundary_key(
    words: List[WordTimestamp], preceding_index: int
) -> Optional[Tuple[str, str]]:
    """Stable word-boundary identity independent of list-index differences."""
    if preceding_index < 0 or preceding_index + 1 >= len(words):
        return None
    left = normalize_token(words[preceding_index].word)
    right = normalize_token(words[preceding_index + 1].word)
    return (left, right) if left and right else None


# ═══════════════════════════════════════════════════════════════════════════════
# Step 2: Acoustic Feature Extraction
# ═══════════════════════════════════════════════════════════════════════════════


class AcousticExtractor:
    """
    Extracts pitch (F0 in Hz & semitones), energy (RMS & dB), and pacing metrics.
    Maintains strictly separate timestamp arrays for each feature to prevent misalignment.
    """

    def __init__(
        self,
        audio_path: str,
        words: List[WordTimestamp],
        config: Optional[EvaluatorConfig] = None,
    ):
        self.path = audio_path
        self.words = words
        self.config = config or EvaluatorConfig()

        # Load audio
        self.y, self.sr, self.duration = validate_audio_file(audio_path, self.config)

        cache_root = (
            Path(self.config.cache_dir or Path(__file__).parent / "model-artifacts")
            / "features"
        )
        cache_root.mkdir(parents=True, exist_ok=True)
        settings = {
            k: getattr(self.config, k)
            for k in [
                "sr",
                "hop_length",
                "fmin_hz",
                "fmax_hz",
                "speech_active_db_floor",
                "smooth_win_frames",
            ]
        }
        digest = hashlib.sha256(
            Path(audio_path).read_bytes()
            + json.dumps(settings, sort_keys=True).encode()
            + b"acoustics-v3"
        ).hexdigest()
        cached = cache_root / (digest + ".npz")
        if cached.exists():
            try:
                with np.load(cached, allow_pickle=False) as data:
                    for key in data.files:
                        value = data[key]
                        setattr(self, key, value.item() if value.ndim == 0 else value)
                self._compute_speech_rate()
                return
            except (ValueError, OSError):
                cached.unlink(missing_ok=True)

        # Feature contours
        self._extract_energy()
        self._extract_pitch()
        self._compute_speech_rate()
        spectrum = np.abs(
            librosa.stft(self.y, n_fft=1024, hop_length=self.config.hop_length)
        )
        self.spectral_centroid = librosa.feature.spectral_centroid(
            S=spectrum, sr=self.sr
        )[0]
        self.spectral_times = librosa.frames_to_time(
            np.arange(spectrum.shape[1]), sr=self.sr, hop_length=self.config.hop_length
        )
        self.mfcc = librosa.feature.mfcc(
            y=self.y,
            sr=self.sr,
            n_mfcc=13,
            n_fft=1024,
            hop_length=self.config.hop_length,
        )
        values = {
            key: value
            for key, value in self.__dict__.items()
            if key != "y" and isinstance(value, (np.ndarray, float, int))
        }
        temporary = cached.with_suffix("." + uuid4().hex + ".npz")
        np.savez_compressed(temporary, **values)
        temporary.replace(cached)

    # ── Energy Extraction ──────────────────────────────────────────────────

    def _extract_energy(self) -> None:
        """
        Extracts raw RMS energy and converts to dB scale relative to full scale.
        Maintains distinct energy timestamp array.
        """
        rms = librosa.feature.rms(
            y=self.y,
            frame_length=2 * self.config.hop_length,
            hop_length=self.config.hop_length,
        )[0]
        self.energy_rms = rms
        self.energy_times = librosa.frames_to_time(
            np.arange(len(rms)),
            sr=self.sr,
            hop_length=self.config.hop_length,
        )

        # dB scale: 20 * log10(max(rms, 1e-7))
        eps = 1e-7
        self.energy_db = 20.0 * np.log10(np.maximum(rms, eps))

        # Detect speech-active frames via energy threshold
        active_mask = self.energy_db >= self.config.speech_active_db_floor
        self.speech_active_mask = active_mask

        # Speaker gain normalization: median dB of speech-active frames
        if active_mask.any():
            self.median_active_db = float(np.median(self.energy_db[active_mask]))
        else:
            self.median_active_db = float(np.median(self.energy_db))

        # Gain-compensated dB (centered relative to speaker's active median)
        self.energy_db_relative = self.energy_db - self.median_active_db
        self.energy_smooth = uniform_filter1d(
            self.energy_db_relative, size=self.config.smooth_win_frames
        )

    # ── Pitch (F0) Extraction ──────────────────────────────────────────────

    def _extract_pitch(self) -> None:
        """
        Extracts fundamental frequency using pYIN.
        Preserves unvoiced frames as NaN.
        Converts voiced frames to semitones relative to A4 (440 Hz).
        Centers semitones around speaker median to cancel register differences
        WITHOUT compressing variance.
        """
        f0, voiced_flag, _ = librosa.pyin(
            self.y,
            fmin=self.config.fmin_hz,
            fmax=self.config.fmax_hz,
            sr=self.sr,
            hop_length=self.config.hop_length,
            fill_na=np.nan,
        )
        self.f0_hz = f0
        self.voiced_mask = voiced_flag & ~np.isnan(f0) & (f0 > 0)
        self.pitch_times = librosa.frames_to_time(
            np.arange(len(f0)),
            sr=self.sr,
            hop_length=self.config.hop_length,
        )

        # Convert Hz to semitones: 12 * log2(F0 / 440) + 69 (MIDI scale)
        self.f0_semitones = np.full_like(f0, np.nan)
        voiced_idx = np.where(self.voiced_mask)[0]

        if len(voiced_idx) > 0:
            hz_voiced = f0[voiced_idx]
            st_voiced = 12.0 * np.log2(hz_voiced / 440.0) + 69.0
            self.f0_semitones[voiced_idx] = st_voiced

            # Median-centering: subtract median pitch of the speaker
            # This aligns registers (e.g. male ~120Hz vs female ~220Hz) while keeping true variance intact
            self.speaker_median_st = float(np.median(st_voiced))
            self.f0_centered_st = np.full_like(f0, np.nan)
            self.f0_centered_st[voiced_idx] = st_voiced - self.speaker_median_st

            # Statistics
            self.pitch_std_st = float(np.std(st_voiced))
            q75, q25 = np.percentile(st_voiced, [75, 25])
            self.pitch_iqr_st = float(q75 - q25)
            p95, p05 = np.percentile(st_voiced, [95, 5])
            self.pitch_range_st = float(p95 - p05)
            self.voiced_ratio = float(len(voiced_idx) / len(f0))
        else:
            self.speaker_median_st = 0.0
            self.f0_centered_st = np.full_like(f0, np.nan)
            self.pitch_std_st = 0.0
            self.pitch_iqr_st = 0.0
            self.pitch_range_st = 0.0
            self.voiced_ratio = 0.0

        # Create a finite interpolated contour for DTW alignment
        # Unvoiced regions linearly interpolated to avoid NaN breaking DTW
        self.f0_smooth_for_dtw = self._build_finite_pitch_contour()

    def _build_finite_pitch_contour(self) -> np.ndarray:
        """Interpolate only for DTW mechanics; detector statistics still use voiced_mask.

        Unvoiced frames are never replaced with artificial zero-pitch values. The
        original mask remains authoritative and is required for all pitch statistics.
        """
        values = np.asarray(self.f0_centered_st, dtype=float)
        valid = self.voiced_mask & np.isfinite(values)
        if not valid.any():
            return np.full(values.shape, np.nan, dtype=float)
        indices = np.arange(len(values))
        # Endpoint extension avoids a zero-valued artificial contour before/after speech.
        filled = np.interp(indices, indices[valid], values[valid])
        return uniform_filter1d(filled, size=max(1, self.config.smooth_win_frames))

    # ── Speech Rate & Pauses ───────────────────────────────────────────────

    def _compute_speech_rate(self) -> None:
        """
        Computes global WPM, articulation rate (excluding pauses), and detects pauses
        with word and sentence context.
        """
        if len(self.words) < 2:
            self.rate_metrics = SpeechRateMetrics(
                total_words=len(self.words),
                duration_sec=self.duration,
                spoken_duration_sec=self.duration,
                speech_active_sec=self.duration,
                global_wpm=0.0,
                articulation_wpm=0.0,
                pauses=[],
            )
            return

        spoken_start = self.words[0].start
        spoken_end = self.words[-1].end
        spoken_duration = max(0.1, spoken_end - spoken_start)

        # Detect pauses between words
        pauses = []
        total_pause_duration = 0.0

        for i in range(1, len(self.words)):
            w_prev = self.words[i - 1]
            w_next = self.words[i]
            gap = w_next.start - w_prev.end

            if gap >= self.config.pause_min_sec:
                # Check if gap occurs at sentence boundary (preceding word has punctuation)
                is_sentence_end = bool(re.search(r"[.!?]$", w_prev.word))
                pause_info = {
                    "start": round(w_prev.end, 4),
                    "end": round(w_next.start, 4),
                    "duration": round(gap, 4),
                    "preceding_word": w_prev.word,
                    "following_word": w_next.word,
                    "is_sentence_boundary": is_sentence_end,
                    "word_index": i - 1,
                    "boundary_key": (_pause_boundary_key(self.words, i - 1)),
                }
                pauses.append(pause_info)
                total_pause_duration += gap

        speech_active_duration = max(0.1, spoken_duration - total_pause_duration)
        global_wpm = (len(self.words) / spoken_duration) * 60.0
        articulation_wpm = (len(self.words) / speech_active_duration) * 60.0

        self.rate_metrics = SpeechRateMetrics(
            total_words=len(self.words),
            duration_sec=self.duration,
            spoken_duration_sec=round(spoken_duration, 4),
            speech_active_sec=round(speech_active_duration, 4),
            global_wpm=round(global_wpm, 2),
            articulation_wpm=round(articulation_wpm, 2),
            pauses=pauses,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Step 3: Dynamic Time Warping (DTW)
# ═══════════════════════════════════════════════════════════════════════════════


def dtw_align_contours(
    baseline_series: np.ndarray,
    candidate_series: np.ndarray,
    radius: int = 25,
) -> Tuple[np.ndarray, np.ndarray, List[Tuple[int, int]]]:
    """
    Aligns baseline and candidate 1D contours through bounded fallback DTW.
    Returns warped_baseline, warped_candidate, and the alignment path.
    """
    baseline_series = np.asarray(baseline_series, dtype=float).reshape(-1)
    candidate_series = np.asarray(candidate_series, dtype=float).reshape(-1)

    def finite_for_alignment(values: np.ndarray) -> np.ndarray:
        valid = np.isfinite(values)
        if not valid.any():
            return np.array([], dtype=np.float64)
        ix = np.arange(len(values))
        return np.interp(ix, ix[valid], values[valid]).reshape(-1, 1).astype(np.float64)

    bl = finite_for_alignment(baseline_series)
    cd = finite_for_alignment(candidate_series)
    if len(bl) == 0 or len(cd) == 0:
        return np.array([]), np.array([]), []

    # Bounded fallback DTW. Detectors use text-constrained correspondence below.
    bi = np.linspace(0, len(bl) - 1, min(800, len(bl)), dtype=int)
    ci = np.linspace(0, len(cd) - 1, min(800, len(cd)), dtype=int)
    _, path = librosa.sequence.dtw(X=bl[bi].T, Y=cd[ci].T, metric="euclidean")
    path_list = [(int(bi[i]), int(ci[j])) for i, j in path[::-1]]

    warped_bl = np.array(
        [baseline_series[min(i, len(baseline_series) - 1)] for i, _ in path_list]
    )
    warped_cd = np.array(
        [candidate_series[min(j, len(candidate_series) - 1)] for _, j in path_list]
    )

    return warped_bl, warped_cd, path_list


# ═══════════════════════════════════════════════════════════════════════════════
# Step 4: Flaw Detection & Temporal Grounding
# ═══════════════════════════════════════════════════════════════════════════════


class FlawDetector:
    """Contrastive detection constrained by matching words and actual time windows."""

    def __init__(self, baseline_ext, candidate_ext, config=None):
        self.bl, self.cd = baseline_ext, candidate_ext
        self.config = config or EvaluatorConfig()
        self.warnings = []

    def run_all(self):
        from delivery_analysis import detect_delivery_flaws

        data, self.warnings = detect_delivery_flaws(self.bl, self.cd, self.config)
        result = []
        for item in data:
            item["evidence"] = EvidenceData(**item["evidence"])
            result.append(FlawRegion(**item))
        return result


def merge_overlapping_flaws(
    flaws: List[FlawRegion], max_gap_sec: float = 0.5
) -> List[FlawRegion]:
    """
    Merges overlapping or adjacent flaw intervals of the SAME flaw type.
    Avoids multi-window penalty accumulation on the same physical speech flaw.
    """
    if not flaws:
        return []

    # Group by flaw_type
    by_type: Dict[str, List[FlawRegion]] = {}
    for f in flaws:
        by_type.setdefault(f.flaw_type, []).append(f)

    merged_all: List[FlawRegion] = []

    for f_type, group in by_type.items():
        # Global pacing flaws are file-wide; keep single instance
        if f_type in ("rushed_pacing", "slow_pacing"):
            # Sort by severity descending and take highest
            group.sort(key=lambda x: x.severity, reverse=True)
            merged_all.append(group[0])
            continue

        group.sort(key=lambda x: x.start_time)
        current = group[0]

        for next_f in group[1:]:
            # If overlapping or within max_gap_sec, merge
            if next_f.start_time <= current.end_time + max_gap_sec:
                # Merge: span start to max end, keep maximum severity
                new_start = current.start_time
                new_end = max(current.end_time, next_f.end_time)
                max_sev = max(current.severity, next_f.severity)
                max_conf = max(current.confidence, next_f.confidence)

                # Combine transcript excerpts if available
                words = []
                if current.transcript_excerpt:
                    words.extend(current.transcript_excerpt.split())
                if next_f.transcript_excerpt:
                    for w in next_f.transcript_excerpt.split():
                        if w not in words:
                            words.append(w)
                combined_excerpt = " ".join(words) if words else None

                current = FlawRegion(
                    flaw_type=f_type,
                    start_time=new_start,
                    end_time=new_end,
                    severity=max_sev,
                    confidence=max_conf,
                    description=current.description,
                    causal_explanation=current.causal_explanation,
                    evidence=current.evidence,
                    measured_value=current.measured_value,
                    threshold=current.threshold,
                    reference_value=current.reference_value,
                    transcript_excerpt=combined_excerpt,
                    recommendation=current.recommendation,
                )
            else:
                merged_all.append(current)
                current = next_f

        merged_all.append(current)

    return merged_all


# ═══════════════════════════════════════════════════════════════════════════════
# Step 5: Rubric Scoring Engine
# ═══════════════════════════════════════════════════════════════════════════════


def compute_rubric_scores(
    flaws: List[FlawRegion],
    config: Optional[EvaluatorConfig] = None,
    duration: Optional[float] = None,
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """
    Computes bounded, transparent rubric scores (0–100):
    - Overall score
    - Pacing score (affected by rushed/slow pacing, awkward pauses)
    - Intonation score (affected by monotone delivery)
    - Energy score (affected by low energy dips)
    """
    config = config or EvaluatorConfig()

    pacing_score = 100.0
    intonation_score = 100.0
    energy_score = 100.0

    deductions_log: List[Dict[str, Any]] = []

    for f in flaws:
        if f.flaw_type == "recognition_difficulty":
            continue  # Clarity is scored directly from excess WER, once per recording.
        base_deduction = float(config.deduction_weights.get(f.flaw_type, 4))
        # Severity multiplier: 1=0.7x, 2=1.0x, 3=1.3x, 4=1.6x, 5=2.0x
        sev_mult = 0.7 + (f.severity - 1) * 0.325
        region_duration = max(
            f.end_time - f.start_time,
            f.evidence.additional.get("reference_region_seconds", 0),
        )
        exposure = min(1.0, region_duration / duration) if duration else 0.2
        deduction = round(base_deduction * sev_mult * exposure * 5, 1)

        deductions_log.append(
            {
                "flaw_type": f.flaw_type,
                "interval": [f.start_time, f.end_time],
                "severity": f.severity,
                "points_deducted": deduction,
                "duration_fraction": round(exposure, 4),
            }
        )

        if f.flaw_type in ("rushed_pacing", "slow_pacing", "awkward_pause"):
            pacing_score -= deduction
        elif f.flaw_type == "monotone_delivery":
            intonation_score -= deduction
        elif f.flaw_type == "low_energy":
            energy_score -= deduction

    # Clamp subscores to [0, 100]
    pacing_score = max(0.0, min(100.0, pacing_score))
    intonation_score = max(0.0, min(100.0, intonation_score))
    energy_score = max(0.0, min(100.0, energy_score))

    # Overall weighted average (Pacing: 40%, Intonation: 35%, Energy: 25%)
    overall = (0.40 * pacing_score) + (0.35 * intonation_score) + (0.25 * energy_score)
    overall = round(max(0.0, min(100.0, overall)), 1)

    scores = {
        "overall": overall,
        "pacing": round(pacing_score, 1),
        "intonation": round(intonation_score, 1),
        "energy": round(energy_score, 1),
    }

    scoring_metadata = {
        "formula": "overall = 0.40 * pacing + 0.35 * intonation + 0.25 * energy",
        "deductions": deductions_log,
        "status": "evaluated_heuristic",
    }

    return scores, scoring_metadata


def generate_summary(
    scores: Dict[str, float],
    flaws: List[FlawRegion],
    warnings_list: List[str],
) -> str:
    """Produces an accurate, honest summary without overclaiming flawless delivery."""
    n = len(flaws)
    if n == 0:
        base = (
            f"No delivery flaws were detected by the current rule set within tested parameters. "
            f"Overall heuristic score: {scores['overall']}/100."
        )
    else:
        types_str = ", ".join(sorted({f.flaw_type.replace("_", " ") for f in flaws}))
        base = (
            f"The candidate scored {scores['overall']}/100 overall with {n} flagged delivery region(s) "
            f"spanning: {types_str}. "
            f"Sub-scores: Pacing {scores['pacing']}, Intonation {scores['intonation']}, Energy {scores['energy']}."
        )

    if warnings_list:
        base += (
            f" Note: {len(warnings_list)} acoustic condition warning(s) were logged."
        )
    return base


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Sanitization Helper
# ═══════════════════════════════════════════════════════════════════════════════


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively converts NumPy scalars, NaNs, and infinities into safe JSON types.
    NaN/inf values become None.
    """
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]
    if isinstance(obj, (np.floating, float)):
        val = float(obj)
        return None if (math.isnan(val) or math.isinf(val)) else round(val, 4)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return sanitize_for_json(obj.tolist())
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def build_time_series_payload(bl_ext, cd_ext, max_points=600):
    """Map the reference into participant time using corresponding word boundaries."""
    from delivery_analysis import anchors, mapped_feature

    points, _ = anchors(bl_ext.words, cd_ext.words)
    output = {
        "time_axis": "participant_aligned",
        "alignment_method": "piecewise word-boundary mapping",
    }

    def store(name, key, times, reference, candidate):
        valid = times <= cd_ext.duration
        times, reference, candidate = times[valid], reference[valid], candidate[valid]
        indices = np.linspace(0, len(times) - 1, min(max_points, len(times)), dtype=int)

        def values(array):
            return [
                round(float(array[i]), 4) if np.isfinite(array[i]) else None
                for i in indices
            ]

        clock = [round(float(times[i]), 4) for i in indices]
        output[f"baseline_{name}_timestamps"] = clock
        output[f"candidate_{name}_timestamps"] = clock
        output[f"baseline_{key}"] = values(reference)
        output[f"candidate_{key}"] = values(candidate)

    for name, key, candidate in [
        ("pitch", "f0_semitones", cd_ext.f0_centered_st),
        ("energy", "energy_db", cd_ext.energy_db_relative),
    ]:
        times, reference = mapped_feature(bl_ext, cd_ext, name)
        store(name, key, times, reference, candidate)
    for name, bl_values, cd_values in [
        ("spectral_centroid", bl_ext.spectral_centroid, cd_ext.spectral_centroid),
        ("mfcc_2", bl_ext.mfcc[1], cd_ext.mfcc[1]),
    ]:
        times = cd_ext.spectral_times
        reference = np.interp(
            np.interp(times, points[:, 0], points[:, 1]),
            bl_ext.spectral_times,
            bl_values,
        )
        reference[(times < points[0, 0]) | (times > points[-1, 0])] = np.nan
        store(name, name, times, reference, cd_values)
    times = np.arange(0, cd_ext.duration, 0.25)

    def rate(words, clock):
        result = []
        for t in clock:
            start, end = max(words[0].start, t - 2), min(words[-1].end, t + 2)
            if end <= start:
                result.append(np.nan)
            else:
                # Fractional boundary words avoid quantization from short windows.
                count = sum(
                    max(0, min(w.end, end) - max(w.start, start))
                    / max(0.01, w.end - w.start)
                    for w in words
                )
                result.append(count * 60 / (end - start))
        return np.asarray(result)

    reference = rate(bl_ext.words, np.interp(times, points[:, 0], points[:, 1]))
    reference[(times < points[0, 0]) | (times > points[-1, 0])] = np.nan
    store("pacing", "wpm", times, reference, rate(cd_ext.words, times))
    return output


# ═══════════════════════════════════════════════════════════════════════════════
# High-Level Evaluator Interface
# ═══════════════════════════════════════════════════════════════════════════════


def evaluate(
    baseline_path: str,
    candidate_path: str,
    transcript: Optional[str] = None,
    device: str = "cpu",
    language: str = "en",
    output_path: Optional[str] = None,
    config: Optional[EvaluatorConfig] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> Dict[str, Any]:
    """
    End-to-end contrastive speech evaluation pipeline.

    Parameters
    ----------
    baseline_path : str
        Path to reference ("good") audio file.
    candidate_path : str
        Path to candidate audio file.
    transcript : Optional[str]
        Confirmed/corrected shared transcript. If omitted, candidate audio is transcribed
        automatically. A UI should call transcribe_audio first, let the user correct it,
        then pass the confirmed text here.
    device : str
        Compute device ("cpu" or "cuda").
    language : str
        Spoken language code ("en").
    output_path : Optional[str]
        Path to write output JSON report.
    config : Optional[EvaluatorConfig]
        Pipeline tuning configuration.
    progress_callback : Optional[Callable]
        Website job progress and cooperative cancellation between pipeline stages.

    Returns
    -------
    Dict[str, Any]
        Standardized, JSON-safe evaluation report.
    """
    if config is None:
        config = EvaluatorConfig()

    def progress(stage: str, percent: float) -> None:
        if progress_callback is not None:
            progress_callback(stage, percent)

    progress("Preparing speech evaluation", 5.0)
    transcript_source = (
        "user_confirmed" if transcript and transcript.strip() else "automatic"
    )
    if not transcript or not transcript.strip():
        progress("Transcribing participant audio", 10.0)
        transcript = transcribe_audio(candidate_path, device=device, language=language)
    transcript = transcript.strip()
    if not transcript:
        raise ValueError(
            "Transcription produced an empty transcript. Supply a corrected transcript and retry."
        )

    log.info("═══ Starting Contrastive Speech Evaluation ═══")
    log.info("Baseline : %s", baseline_path)
    log.info("Candidate: %s", candidate_path)

    # 1. Forced Alignment
    progress("Aligning reference words", 15.0)
    bl_words = align_audio(
        baseline_path, transcript, device=device, language=language, config=config
    )
    progress("Aligning participant words", 30.0)
    cd_words = align_audio(
        candidate_path, transcript, device=device, language=language, config=config
    )

    # 2. Acoustic Feature Extraction
    progress("Measuring reference pitch, energy and pacing", 45.0)
    bl_ext = AcousticExtractor(baseline_path, bl_words, config=config)
    progress("Measuring participant pitch, energy and pacing", 60.0)
    cd_ext = AcousticExtractor(candidate_path, cd_words, config=config)

    log.info(
        "Baseline  — WPM: %.1f | Pauses: %d | Duration: %.2fs",
        bl_ext.rate_metrics.global_wpm,
        len(bl_ext.rate_metrics.pauses),
        bl_ext.duration,
    )
    log.info(
        "Candidate — WPM: %.1f | Pauses: %d | Duration: %.2fs",
        cd_ext.rate_metrics.global_wpm,
        len(cd_ext.rate_metrics.pauses),
        cd_ext.duration,
    )

    # 3 & 4. Flaw Detection & Grounding
    progress("Detecting delivery flaws", 75.0)
    detector = FlawDetector(bl_ext, cd_ext, config=config)
    flaws = detector.run_all()
    warnings_list = list(detector.warnings)

    clarity = None
    if config.enable_clarity:
        from clarity_analysis import compare_recognition

        progress("Recognizing reference speech for clarity", 78.0)
        reference_text = speech_runtime.recognize_for_clarity(
            baseline_path,
            model_name=config.asr_model,
            language=language,
            cache_dir=config.cache_dir,
            cpu_threads=config.cpu_threads,
        )
        progress("Recognizing participant speech for clarity", 84.0)
        participant_text = speech_runtime.recognize_for_clarity(
            candidate_path,
            model_name=config.asr_model,
            language=language,
            cache_dir=config.cache_dir,
            cpu_threads=config.cpu_threads,
        )
        clarity, clarity_flaws = compare_recognition(
            transcript, reference_text, participant_text, cd_words, config.asr_model
        )
        for item in clarity_flaws:
            item["evidence"] = EvidenceData(**item["evidence"])
            flaws.append(FlawRegion(**item))
        flaws.sort(key=lambda f: (f.start_time, f.end_time, f.flaw_type))
        warnings_list.append(
            "Clarity is reference-relative ASR recoverability, not a calibrated human intelligibility or accent score. Recognition errors may reflect recording conditions or model bias."
        )
        if not clarity["available"]:
            warnings_list.append(clarity["reason"])

    # 5. Rubric Scoring
    progress("Scoring delivery and preparing plots", 90.0)
    scores, scoring_meta = compute_rubric_scores(
        flaws, config=config, duration=cd_ext.duration
    )
    scores["clarity"] = clarity["score"] if clarity else None
    pitch_available = (
        bl_ext.voiced_ratio >= config.min_voiced_ratio
        and cd_ext.voiced_ratio >= config.min_voiced_ratio
        and np.sum(bl_ext.voiced_mask) >= config.min_voiced_frames
        and np.sum(cd_ext.voiced_mask) >= config.min_voiced_frames
        and bl_ext.pitch_std_st >= config.min_baseline_semitone_std
    )
    if not pitch_available:
        scores["intonation"] = None
        scores["overall"] = round(
            (0.40 * scores["pacing"] + 0.25 * scores["energy"]) / 0.65, 1
        )
        warnings_list.append(
            "Pitch scoring unavailable: insufficient voiced variation in the reference or participant."
        )
    # The standalone default rubric includes clarity only when measured.
    standalone_weights = (
        {"pacing": 0.30, "intonation": 0.25, "energy": 0.25, "clarity": 0.20}
        if config.enable_clarity
        else {"pacing": 0.40, "intonation": 0.35, "energy": 0.25}
    )
    available_scores = {
        k: v for k, v in scores.items() if k in standalone_weights and v is not None
    }
    scores["overall"] = round(
        sum(standalone_weights[k] * v for k, v in available_scores.items())
        / sum(standalone_weights[k] for k in available_scores),
        1,
    )
    scoring_meta["clarity_method"] = clarity["method"] if clarity else None
    scoring_meta["standalone_weights"] = standalone_weights
    scoring_meta["formula"] = (
        "Weighted mean of available standalone dimensions; clarity = 100 * (1 - min(1, max(0, participant_WER - reference_WER)))."
    )
    summary_text = generate_summary(scores, flaws, warnings_list)
    time_series = build_time_series_payload(bl_ext, cd_ext)

    # Assemble report structure
    flaws_serialized = []
    for f in flaws:
        f_dict = asdict(f)
        flaws_serialized.append(f_dict)

    report: Dict[str, Any] = {
        "scores": scores,
        "summary": summary_text,
        "flaw_regions": flaws_serialized,
        "time_series_data": time_series,
        "word_alignments": {
            "baseline": [asdict(w) for w in bl_words],
            "candidate": [asdict(w) for w in cd_words],
        },
        "acoustic_statistics": {
            "baseline": {
                "duration_seconds": float(bl_ext.duration),
                "global_wpm": bl_ext.rate_metrics.global_wpm,
                "articulation_wpm": bl_ext.rate_metrics.articulation_wpm,
                "pitch_std_semitones": round(bl_ext.pitch_std_st, 2),
                "pitch_iqr_semitones": round(bl_ext.pitch_iqr_st, 2),
                "voiced_ratio": round(bl_ext.voiced_ratio, 2),
                "median_energy_db": round(bl_ext.median_active_db, 2),
                "pause_count": len(bl_ext.rate_metrics.pauses),
            },
            "candidate": {
                "duration_seconds": float(cd_ext.duration),
                "global_wpm": cd_ext.rate_metrics.global_wpm,
                "articulation_wpm": cd_ext.rate_metrics.articulation_wpm,
                "pitch_std_semitones": round(cd_ext.pitch_std_st, 2),
                "pitch_iqr_semitones": round(cd_ext.pitch_iqr_st, 2),
                "voiced_ratio": round(cd_ext.voiced_ratio, 2),
                "median_energy_db": round(cd_ext.median_active_db, 2),
                "pause_count": len(cd_ext.rate_metrics.pauses),
            },
        },
        "scoring_metadata": scoring_meta,
        "clarity": clarity,
        "transcript": transcript,
        "transcript_source": transcript_source,
        "measurement_availability": {
            "pitch": bool(pitch_available),
            "clarity": bool(clarity and clarity["available"]),
        },
        "warnings": warnings_list,
        "metadata": {
            "version": "3.1.0",
            "device": device,
            "language": language,
        },
    }

    # Sanitize against any NaN / Inf
    safe_report = sanitize_for_json(report)

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(
            json.dumps(safe_report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log.info("Report saved to %s", output_path)

    return safe_report


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Contrastive Speech Delivery Evaluator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--baseline", required=True, help="Path to reference (good) audio file"
    )
    parser.add_argument(
        "--candidate", required=True, help="Path to candidate audio file"
    )
    parser.add_argument("--text", help="Path to shared transcript .txt file")
    parser.add_argument(
        "--transcript",
        help="Confirmed/corrected transcript text; omit to transcribe candidate audio automatically",
    )
    parser.add_argument(
        "--output", default="evaluation_report.json", help="Output JSON report path"
    )
    parser.add_argument(
        "--device", default="cpu", choices=["cpu", "cuda"], help="Compute device"
    )
    parser.add_argument("--language", default="en", help="Language code (default: en)")

    args = parser.parse_args()

    # Determine transcript
    transcript_text = ""
    if args.text:
        t_path = Path(args.text)
        if not t_path.is_file():
            log.error("Transcript file not found: %s", args.text)
            sys.exit(1)
        transcript_text = t_path.read_text(encoding="utf-8").strip()
    elif args.transcript:
        transcript_text = args.transcript.strip()
    # When neither is supplied, evaluate() transcribes the candidate first. A web UI
    # should call transcribe_audio(), let the user edit/confirm, then pass that text in.

    if transcript_text and not transcript_text.strip():
        log.error("Transcript is empty.")
        sys.exit(1)

    try:
        report = evaluate(
            baseline_path=args.baseline,
            candidate_path=args.candidate,
            transcript=transcript_text,
            device=args.device,
            language=args.language,
            output_path=args.output,
        )
    except Exception as exc:
        log.error("Evaluation failed: %s", exc)
        sys.exit(1)

    print("\n" + "=" * 55)
    print("           SPEECH EVALUATION REPORT")
    print("=" * 55)
    print(f"  Overall Score : {report['scores']['overall']}/100")
    print(f"  Pacing        : {report['scores']['pacing']}/100")
    print(f"  Intonation    : {report['scores']['intonation']}/100")
    print(f"  Energy        : {report['scores']['energy']}/100")
    print(f"  Flaws Flagged : {len(report['flaw_regions'])}")
    if report["warnings"]:
        print(f"  Warnings      : {len(report['warnings'])}")
    print("=" * 55)
    print(f"  Summary: {report['summary']}")
    print(f"  Report saved to: {args.output}\n")


if __name__ == "__main__":
    main()
