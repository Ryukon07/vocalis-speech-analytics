"""Adapt the supplied evaluator.py to the website's persisted result contract."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import threading
from uuid import NAMESPACE_URL, uuid5

from app.core.exceptions import AppError
from app.schemas.contracts import (
    Alignment,
    AnalysisResult,
    Evidence,
    Flaw,
    Point,
    Scores,
    Series,
    Word,
)
from .base import SpeechAnalysisProvider
from .schemas import Capabilities, ProviderHealth, ProviderRequest


ROOT = Path(__file__).resolve().parents[3]
ENGINE_PATH = ROOT / "evaluator.py"
VERSION = "3.1.3-local.1"
DEPENDENCIES = (
    "librosa",
    "numpy",
    "scipy",
    "soundfile",
    "torch",
    "torchaudio",
    "faster_whisper",
    "num2words",
    "truststore",
    "av",
)
CATEGORIES = ["pacing", "pitch", "energy", "pausing", "clarity"]
FLAW_CATEGORIES = {
    "monotone_delivery": "pitch",
    "rushed_pacing": "pacing",
    "slow_pacing": "pacing",
    "awkward_pause": "pausing",
    "low_energy": "energy",
    "recognition_difficulty": "clarity",
}
_ENGINE = None
_IMPORT_LOCK = threading.Lock()
_EVALUATION_LOCK = threading.Lock()


def _load_engine():
    """Import expensive ML libraries only for a real analysis, once per process."""
    global _ENGINE
    with _IMPORT_LOCK:
        if _ENGINE is None:
            spec = importlib.util.spec_from_file_location(
                "_vocalis_evaluator", ENGINE_PATH
            )
            if spec is None or spec.loader is None:
                raise AppError(
                    "PROVIDER_UNAVAILABLE", "The evaluator module is missing.", 503
                )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            try:
                spec.loader.exec_module(module)
            except Exception as exc:
                sys.modules.pop(spec.name, None)
                raise AppError(
                    "PROVIDER_UNAVAILABLE",
                    "The evaluator's Python packages could not be loaded. Use the Python environment "
                    "that runs evaluator.py and install the backend requirements in that environment.",
                    503,
                ) from exc
            _ENGINE = module
    return _ENGINE


def _series(report, feature, value_key, unit):
    data = report.get("time_series_data", {})
    roles = {}
    for role, prefix in (("participant", "candidate"), ("reference", "baseline")):
        times = data.get(f"{prefix}_{feature}_timestamps", [])
        values = data.get(f"{prefix}_{value_key}", [])
        if len(times) != len(values):
            raise ValueError("Evaluator returned inconsistent feature arrays")
        roles[role] = [Point(time_seconds=t, value=v) for t, v in zip(times, values)]
    return Series(
        unit=unit,
        time_axis=data.get("time_axis", "recording"),
        window_metadata={
            "source": "evaluator.py",
            "alignment": data.get("alignment_method", "independent recording clocks"),
        },
        **roles,
    )


class CustomSpeechAnalysisProvider(SpeechAnalysisProvider):
    def __init__(self, settings=None):
        self.settings = settings

    def health_check(self):
        if not ENGINE_PATH.is_file():
            return ProviderHealth(
                ready=False,
                message="Place evaluator.py in the project root before starting real analysis.",
            )
        missing = [
            name for name in DEPENDENCIES if importlib.util.find_spec(name) is None
        ]
        if missing:
            return ProviderHealth(
                ready=False,
                message="Evaluator dependencies missing: " + ", ".join(missing) + ". "
                "Start the API with the same Python environment used for evaluator.py, "
                "or install the project root requirements.txt into the API environment.",
            )
        return ProviderHealth(
            ready=True,
            message="Local English speech processing is available. CPU inference uses cached pretrained models; "
            "the first use downloads any missing weights.",
        )

    def get_capabilities(self):
        health = self.health_check()
        return Capabilities(
            provider_name="evaluator",
            provider_version=VERSION,
            execution_mode="real",
            ready=health.ready,
            requires_transcript=True,
            requires_reference=True,
            automatic_transcription=True,
            comparison_modes=["recording"],
            categories=CATEGORIES,
            supports_windows=True,
            supports_cancellation=True,
            message=health.message,
        )

    def analyze(self, request: ProviderRequest, progress_callback=None):
        if request.reference_path is None:
            raise AppError(
                "REFERENCE_REQUIRED",
                "Upload or select a reference speech for comparison.",
            )
        transcript = request.transcript.strip()
        if request.settings.comparison_mode != "recording":
            raise AppError(
                "UNSUPPORTED_MODE", "The evaluator compares two audio recordings."
            )
        if not set(request.settings.enabled_categories) <= set(CATEGORIES):
            raise AppError(
                "UNSUPPORTED_CATEGORY",
                "This evaluator supports pacing, pitch, energy, pausing and clarity.",
            )
        if progress_callback:
            progress_callback("Loading speech evaluator", 2.0)
        engine = _load_engine()
        config = engine.EvaluatorConfig()
        config.cache_dir = str(
            getattr(
                self.settings, "model_cache_root", ROOT / "model-artifacts"
            ).resolve()
        )
        config.cpu_threads = getattr(self.settings, "cpu_threads", 4)
        config.enable_clarity = "clarity" in request.settings.enabled_categories
        config.asr_model = getattr(self.settings, "asr_model", "base.en")
        config.window_sec = request.settings.window_seconds
        config.window_step_sec = max(
            0.1, config.window_sec * (1 - request.settings.overlap)
        )
        # Higher sensitivity narrows tolerated contrastive deviations.
        factor = 1.25 - request.settings.sensitivity * 0.5
        config.rushed_wpm_ratio = 1 + 0.30 * factor
        config.slow_wpm_ratio = 1 - 0.30 * factor
        config.monotone_std_ratio = 0.40 / factor
        config.energy_dip_db_threshold = 12 * factor
        config.awkward_pause_sec = 1.5 * factor
        if progress_callback:
            progress_callback("Waiting for speech evaluation", 3.0)
        with _EVALUATION_LOCK:
            try:
                if not transcript:
                    if progress_callback:
                        progress_callback("Transcribing participant speech", 8.0)
                    transcript = engine.transcribe_audio(
                        str(request.participant_path),
                        device=getattr(self.settings, "evaluator_device", "cpu"),
                        language=getattr(self.settings, "evaluator_language", "en"),
                        model_name=getattr(self.settings, "asr_model", "base.en"),
                        cache_dir=config.cache_dir,
                        cpu_threads=config.cpu_threads,
                    )
                    if not transcript.strip():
                        raise AppError(
                            "EMPTY_TRANSCRIPT",
                            "No speech was recognized. Provide a confirmed transcript.",
                        )
                    # ASR can differ in punctuation. It must still recover the reference's words.
                    if engine._transcript_tokens(
                        transcript
                    ) != engine._transcript_tokens(request.reference_transcript):
                        raise AppError(
                            "TRANSCRIPT_MISMATCH",
                            "Recognized words differ from the reference. Generate, review and correct the transcript before comparison.",
                        )
                    transcript = request.reference_transcript
                report = engine.evaluate(
                    baseline_path=str(request.reference_path),
                    candidate_path=str(request.participant_path),
                    transcript=transcript,
                    config=config,
                    device=getattr(self.settings, "evaluator_device", "cpu"),
                    language=getattr(self.settings, "evaluator_language", "en"),
                    progress_callback=progress_callback,
                )
            except engine.AlignmentError as exc:
                raise AppError(
                    "ALIGNMENT_FAILED",
                    "Word alignment failed. Confirm that both recordings contain the same transcript "
                    "and English language, and that the local alignment model can be loaded.",
                ) from exc
            except ValueError as exc:
                raise AppError(
                    "INVALID_SPEECH_INPUT",
                    "The speech input could not be evaluated. Use non-silent English audio under three minutes and a matching confirmed transcript.",
                ) from exc
        if progress_callback:
            progress_callback("Preparing website report", 95.0)

        enabled = set(request.settings.enabled_categories)
        flaws = []
        for index, item in enumerate(report.get("flaw_regions", [])):
            kind = item["flaw_type"]
            category = FLAW_CATEGORIES[kind]
            if category not in enabled:
                continue
            evidence = item.get("evidence", {})
            # The evaluator also includes word context and a threshold-only source
            # tag. The API keeps context in transcript_text and accepts only numeric
            # additional measurements. Candidate-only measurements remain measured.
            numeric_evidence = {
                key: value
                for key, value in evidence.get("additional", {}).items()
                if value is None
                or isinstance(value, (int, float))
                and math.isfinite(value)
            }
            api_evidence = {
                key: evidence.get(key)
                for key in (
                    "baseline_value",
                    "participant_value",
                    "absolute_deviation",
                    "difference_percent",
                    "normalized_deviation",
                )
            }
            api_evidence.update(
                units=evidence.get("units", ""),
                measurement_name=evidence.get("measurement_name", kind),
                source="measured",
                additional=numeric_evidence,
            )
            flaws.append(
                Flaw(
                    id=str(uuid5(NAMESPACE_URL, f"{request.job_id}:{kind}:{index}")),
                    type=kind,
                    category=category,
                    start_seconds=item["start_time"],
                    end_seconds=item["end_time"],
                    severity=item["severity"],
                    confidence=item.get("confidence"),
                    transcript_text=item.get("transcript_excerpt"),
                    evidence=Evidence.model_validate(api_evidence),
                    interpretation_source="rule",
                    explanation=item.get(
                        "causal_explanation", item.get("description", "")
                    ),
                    recommendation=item.get("recommendation", ""),
                )
            )

        raw_scores = report["scores"]
        deductions = report["scoring_metadata"]["deductions"]
        # Split the evaluator's combined pacing/pausing deductions so a pause is
        # counted once when the website rubric weights both categories.
        pacing = max(
            0.0,
            100.0
            - sum(
                row["points_deducted"]
                for row in deductions
                if row["flaw_type"] in {"rushed_pacing", "slow_pacing"}
            ),
        )
        pausing = max(
            0.0,
            100.0
            - sum(
                row["points_deducted"]
                for row in deductions
                if row["flaw_type"] == "awkward_pause"
            ),
        )
        dimensions = {
            "pacing": round(pacing, 1),
            "pausing": round(pausing, 1),
            "pitch": raw_scores.get("intonation"),
            "energy": raw_scores.get("energy"),
            "clarity": raw_scores.get("clarity"),
        }
        dimensions = {
            name: value if name in enabled else None
            for name, value in dimensions.items()
        }
        available = {
            name: value for name, value in dimensions.items() if value is not None
        }
        weights = request.rubric.weights
        total_weight = sum(weights[name] for name in available)
        overall = (
            round(
                sum(weights[name] * value for name, value in available.items())
                / total_weight,
                2,
            )
            if total_weight
            else None
        )
        stats = report["acoustic_statistics"]
        # No detected pitch flaw is not evidence of perfect delivery if pitch was unavailable.
        if report.get("measurement_availability", {}).get("pitch") is False:
            dimensions["pitch"] = None
            available = {
                name: value for name, value in dimensions.items() if value is not None
            }
            total_weight = sum(weights[name] for name in available)
            overall = (
                round(
                    sum(weights[name] * value for name, value in available.items())
                    / total_weight,
                    2,
                )
                if total_weight
                else None
            )
        warnings = list(report.get("warnings", []))
        if any(
            f.get("evidence", {}).get("source") == "candidate_threshold_only"
            for f in report.get("flaw_regions", [])
        ):
            warnings.append(
                "Some pauses were assessed against candidate-only thresholds because a unique baseline word boundary was unavailable."
            )
        warnings.append(
            "Scores use evaluator.py's heuristic deductions and the selected website rubric. "
            "Pacing and pausing are scored separately. Clarity measures additional ASR word errors relative to the reference."
        )
        if report.get("time_series_data", {}).get("time_axis") != "participant_aligned":
            warnings.append(
                "Reference and participant curves use their own recording clocks."
            )
        return AnalysisResult(
            analysis_id=request.job_id,
            provider_name="evaluator",
            provider_version=VERSION,
            execution_mode="real",
            participant_duration_seconds=stats["candidate"]["duration_seconds"],
            reference_duration_seconds=stats["baseline"]["duration_seconds"],
            scores=Scores(overall=overall, dimensions=dimensions),
            flaws=flaws,
            feature_series=(
                {
                    name: _series(report, name, key, unit)
                    for name, key, unit in [
                        ("pitch", "f0_semitones", "semitones"),
                        ("energy", "energy_db", "dB (relative)"),
                        ("spectral_centroid", "spectral_centroid", "Hz"),
                        ("mfcc_2", "mfcc_2", "coefficient"),
                        ("pacing", "wpm", "words/min"),
                    ]
                    if report.get("time_series_data", {}).get(f"candidate_{key}")
                    is not None
                }
                if request.settings.detailed_plots
                else {}
            ),
            alignment=Alignment(
                words=[
                    Word(
                        text=word["word"],
                        start_seconds=word["start"],
                        end_seconds=word["end"],
                        confidence=word.get("confidence"),
                    )
                    for word in report.get("word_alignments", {}).get("candidate", [])
                ]
            ),
            clarity=report.get("clarity") if "clarity" in enabled else None,
            warnings=warnings,
        )
