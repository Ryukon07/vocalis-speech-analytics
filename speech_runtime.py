"""Small local inference runtime: Faster-Whisper ASR and wav2vec2 CTC alignment.

No diarization models, hosted APIs, invented word timestamps, or model training.
"""

from pathlib import Path
import hashlib
import json
import os
import re
import threading
import unicodedata
import sys
from importlib.metadata import version
import numpy as np

_models = {}
_lock = threading.RLock()
MEDIUM_REVISION = "08e178d48790749d25932bbc082711ddcfdfbc4f"
MEDIUM_SHA256 = "9b45e1009dcc4ab601eff815b61d80e60ce3fd8c74c1a14f4a282258286b51ae"


def cached_model_source(model_name, root):
    """Use a checksum-verified pinned fallback; download it on first use."""
    if model_name == "medium":
        snapshot = (
            root / "whisper" / "models--Systran--faster-whisper-medium"
            / "snapshots" / MEDIUM_REVISION
        )
        if not all((snapshot / name).is_file() for name in
                   ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt")):
            from faster_whisper.utils import download_model
            snapshot = Path(download_model("medium", cache_dir=str(root / "whisper"),
                                           revision=MEDIUM_REVISION))
        with (snapshot / "model.bin").open("rb") as weights:
            if hashlib.file_digest(weights, "sha256").hexdigest() != MEDIUM_SHA256:
                raise ValueError("Cached fallback model checksum failed. Download the model again.")
        return str(snapshot)
    return model_name


class TranscriptionQualityError(ValueError):
    code = "UNRELIABLE_TRANSCRIPT"


def validate_transcription_segments(segments):
    """Reject runaway autoregressive repetition rather than save it as a draft.

    Whisper's compression threshold only triggers fallback. With temperature=0
    alone it can still return the failing output, so drafts need a final guard.
    This is a reliability check, not a pronunciation or human clarity score.
    """
    from collections import Counter

    segments = list(segments)
    candidates = [(segment.text, segment.compression_ratio) for segment in segments]
    # Decoder segment boundaries are not a quality boundary: runaway repetition
    # can be emitted as many individually short segments.
    if segments:
        candidates.append((
            " ".join(segment.text for segment in segments),
            max(segment.compression_ratio for segment in segments),
        ))
    for text, compression_ratio in candidates:
        words = re.findall(r"[a-z']+", text.lower())
        if len(words) < 40:
            continue
        ngrams = [tuple(words[i : i + 5]) for i in range(len(words) - 4)]
        counts = Counter(ngrams)
        repeated_fraction = sum(count - 1 for count in counts.values()) / max(
            1, len(ngrams)
        )
        if (
            compression_ratio > 3.0
            and repeated_fraction > 0.5
            and max(counts.values(), default=0) >= 4
        ):
            raise TranscriptionQualityError(
                "Speech recognition produced unreliable repeated text. Record a shorter clip in a quiet setting and check the microphone, or enter a reviewed transcript manually."
            )
    return segments


def recognize_for_clarity(
    path, model_name="base.en", language="en", cache_dir=None, cpu_threads=4
):
    """Unprompted recognition cached by audio content and decoding configuration."""
    from faster_whisper.audio import decode_audio

    root = configure(cache_dir, cpu_threads)
    signature = hashlib.sha256(
        Path(path).read_bytes()
        + f"clarity-asr-v1:{model_name}:{language}:int8:beam5:vad".encode()
    ).hexdigest()
    target = root / "recognition" / f"{signature}.json"
    with _lock:
        if target.is_file():
            try:
                cached = json.loads(target.read_text(encoding="utf-8"))
                if (
                    isinstance(cached.get("text"), str)
                    and cached.get("signature") == signature
                ):
                    return cached["text"]
            except (ValueError, OSError):
                pass
        audio = decode_audio(str(path), sampling_rate=16000)
        if len(audio) > 16000 * 180:
            raise ValueError("Clarity recognition supports at most three minutes.")
        segments = transcribe_segments(
            audio,
            model_name=model_name,
            language=language,
            cache_dir=root,
            cpu_threads=cpu_threads,
        )
        text = " ".join(segment["text"].strip() for segment in segments).strip()
        target.parent.mkdir(parents=True, exist_ok=True)
        from uuid import uuid4

        temporary = target.with_suffix(f".{uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(dict(signature=signature, text=text)), encoding="utf-8"
        )
        temporary.replace(target)
        return text


def alignment_spelling(word):
    """Expand numeric tokens while retaining one timestamp for the displayed word."""
    from num2words import num2words

    value = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode()
    value = value.replace(",", "")

    def spell(match):
        number, suffix = match.group(1), match.group(2)
        return num2words(int(number), to="ordinal" if suffix else "cardinal").replace(
            "-", " "
        )

    value = re.sub(r"(\d+)(st|nd|rd|th)?", spell, value, flags=re.I)
    return "|".join(re.sub("[^A-Z']", "", part.upper()) for part in value.split())


def configure(cache_dir=None, cpu_threads=4):
    import truststore

    truststore.inject_into_ssl()
    root = Path(cache_dir or Path(__file__).parent / "model-artifacts").resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(root / "huggingface"))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    # The former shared cache reproduced a native access violation in pYIN's
    # gufunc. A fresh cache survives cross-process checks. Isolate regenerated
    # native code by runtime versions rather than reusing that legacy directory.
    native_versions = ":".join(version(name) for name in ("numba", "librosa", "numpy"))
    native_signature = hashlib.sha256(
        f"pitch-native-v2:{sys.implementation.cache_tag}:{native_versions}".encode()
    ).hexdigest()[:16]
    os.environ.setdefault("NUMBA_CACHE_DIR", str(root / "numba-v2" / native_signature))
    import torch

    torch.set_num_threads(cpu_threads)
    torch.hub.set_dir(str(root / "torch"))
    return root


def transcribe(
    path,
    device="cpu",
    model_name="base.en",
    language="en",
    cache_dir=None,
    cpu_threads=4,
):
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio

    root = configure(cache_dir, cpu_threads)
    key = ("asr", device, model_name, str(root))
    with _lock:
        if key not in _models:
            _models[key] = WhisperModel(
                cached_model_source(model_name, root),
                device=device,
                compute_type="int8" if device == "cpu" else "float16",
                cpu_threads=cpu_threads,
                num_workers=1,
                download_root=str(root / "whisper"),
            )
        audio = decode_audio(str(path), sampling_rate=16000)
        if len(audio) > 16000 * 180:
            raise ValueError(
                "Use a speech excerpt of at most three minutes for local processing."
            )
        segments, info = _models[key].transcribe(
            audio,
            language=language,
            beam_size=5,
            temperature=0,
            vad_filter=True,
            word_timestamps=True,
            hallucination_silence_threshold=1.0,
            condition_on_previous_text=False,
        )
        segments = validate_transcription_segments(list(segments))
        return " ".join(segment.text.strip() for segment in segments).strip()


def transcribe_segments(
    audio, model_name="base.en", language="en", cache_dir=None, cpu_threads=4
):
    """Return actual ASR segment boundaries for reproducible excerpt selection."""
    from faster_whisper import WhisperModel

    root = configure(cache_dir, cpu_threads)
    key = ("asr", "cpu", model_name, str(root))
    with _lock:
        if key not in _models:
            _models[key] = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=cpu_threads,
                num_workers=1,
                download_root=str(root / "whisper"),
            )
        segments, _ = _models[key].transcribe(
            np.asarray(audio, dtype=np.float32),
            language=language,
            beam_size=5,
            temperature=0,
            vad_filter=True,
            word_timestamps=True,
            condition_on_previous_text=False,
        )
        return [
            dict(
                text=s.text.strip(),
                start=s.start,
                end=s.end,
                words=[
                    dict(
                        word=w.word.strip(),
                        start=w.start,
                        end=w.end,
                        probability=w.probability,
                    )
                    for w in s.words or []
                ],
            )
            for s in segments
        ]


def align_words(
    audio, transcript, sr=16000, device="cpu", cache_dir=None, cpu_threads=4
):
    import torch
    import torchaudio

    configure(cache_dir, cpu_threads)
    key = ("alignment", device)
    with _lock:
        if key not in _models:
            bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
            _models[key] = (bundle.get_model().to(device).eval(), bundle.get_labels())
        model, labels = _models[key]
        words = transcript.split()
        # Preserve original punctuation in the output; CTC uses only its supported alphabet.
        cleaned = [alignment_spelling(word) for word in words]
        if not cleaned or any(not word for word in cleaned):
            raise ValueError(
                "Alignment requires English words. Remove unsupported standalone symbols from the confirmed transcript."
            )
        dictionary = {label: index for index, label in enumerate(labels)}
        target_text = "|".join(cleaned)
        targets = torch.tensor(
            [[dictionary[c] for c in target_text]], dtype=torch.int32, device=device
        )
        with torch.inference_mode():
            emission, _ = model(
                torch.from_numpy(np.asarray(audio, dtype=np.float32))
                .unsqueeze(0)
                .to(device)
            )
            log_probs = emission.log_softmax(-1)
            if targets.shape[1] >= log_probs.shape[1]:
                raise ValueError(
                    "Transcript is too long for this recording. Check the spoken text."
                )
            path, scores = torchaudio.functional.forced_align(
                log_probs, targets, blank=0
            )
            spans = torchaudio.functional.merge_tokens(
                path[0], scores[0].exp(), blank=0
            )
        if len(spans) != len(target_text):
            raise ValueError("CTC alignment did not recover the complete transcript.")
        ratio = len(audio) / sr / emission.shape[1]
        result, index = [], 0
        for original, clean in zip(words, cleaned):
            token_spans = spans[index : index + len(clean)]
            start, end = token_spans[0].start * ratio, token_spans[-1].end * ratio
            confidence = float(np.mean([float(s.score) for s in token_spans]))
            result.append(
                dict(word=original, start=start, end=end, confidence=confidence)
            )
            index += len(clean) + 1
        return result
