from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from speech_runtime import validate_transcription_segments, TranscriptionQualityError


def test_runaway_repetition_is_rejected():
    segment = SimpleNamespace(
        text="I have to do a lot of testing with my testing. " * 20,
        compression_ratio=11.6,
    )
    with pytest.raises(TranscriptionQualityError, match="unreliable repeated text"):
        validate_transcription_segments([segment])


def test_natural_repetition_and_short_phrases_are_preserved():
    short = SimpleNamespace(
        text="We will try, and we will learn, and we will improve.",
        compression_ratio=3.1,
    )
    assert validate_transcription_segments([short]) == [short]
    varied = SimpleNamespace(
        text=" ".join(f"differentword{i}" for i in range(100)), compression_ratio=1.8
    )
    assert validate_transcription_segments([varied]) == [varied]


def test_repetition_split_across_short_decoder_segments_is_rejected():
    segments = [
        SimpleNamespace(text="I have no idea what to do", compression_ratio=4.35)
        for _ in range(7)
    ]
    with pytest.raises(TranscriptionQualityError, match="unreliable repeated text"):
        validate_transcription_segments(iter(segments))


def test_varied_multi_segment_speech_is_preserved():
    segments = [
        SimpleNamespace(text="We gather today to discuss practical changes for our community.", compression_ratio=1.4),
        SimpleNamespace(text="Everyone can help by sharing their experience and proposing a clear next step.", compression_ratio=1.5),
        SimpleNamespace(text="We will review the results together and listen carefully to different perspectives.", compression_ratio=1.3),
        SimpleNamespace(text="Our aim is to build a useful plan that people can put into practice.", compression_ratio=1.6),
    ]
    assert validate_transcription_segments(segments) == segments


def test_corrupt_fallback_weights_are_rejected_before_inference(tmp_path):
    from speech_runtime import cached_model_source, MEDIUM_REVISION
    snapshot = tmp_path / "whisper" / "models--Systran--faster-whisper-medium" / "snapshots" / MEDIUM_REVISION
    snapshot.mkdir(parents=True)
    for name in ("config.json", "tokenizer.json", "vocabulary.txt", "model.bin"):
        (snapshot / name).write_bytes(b"corrupt weights")
    with pytest.raises(ValueError, match="checksum failed"):
        cached_model_source("medium", tmp_path)
