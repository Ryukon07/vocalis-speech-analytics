"""Clarity score evidence, guardrails and rubric integration."""

from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from clarity_analysis import normalized_tokens, word_errors, compare_recognition

TEXT = "We speak these words clearly to share our ideas with everyone today"


def test_normalization_handles_punctuation_numbers_contractions_and_accents():
    assert normalized_tokens("We can't read 19 naïve words.") == normalized_tokens(
        "WE CAN NOT read nineteen naive words!"
    )
    assert normalized_tokens("one-thousand") == normalized_tokens("1,000")
    assert normalized_tokens("a—word") == ["a", "word"]


def test_wer_counts_all_edit_types_and_can_exceed_one():
    result = word_errors(["one", "two", "three"], ["one", "wrong"])
    assert result["errors"] == 2
    assert result["substitutions"] == result["deletions"] == 1
    assert sum(result["token_errors"]) == 2
    assert word_errors(["one"], ["wrong", "extra", "words"])["word_error_rate"] == 3


def test_reference_relative_score_is_bounded_and_not_a_double_pause_penalty():
    equal, _ = compare_recognition(TEXT, TEXT, TEXT)
    assert equal["score"] == 100
    wrong, _ = compare_recognition(TEXT, TEXT, "garbage " * 40)
    assert wrong["score"] == 0
    corrected, _ = compare_recognition(TEXT, TEXT.replace("today", "now"), TEXT)
    assert corrected["score"] == 100


@pytest.mark.parametrize(
    "transcript,reference", [("too few words", "too few words"), (TEXT, "wrong words")]
)
def test_insufficient_or_unreliable_reference_is_unavailable(transcript, reference):
    result, flaws = compare_recognition(transcript, reference, transcript)
    assert not result["available"] and result["score"] is None and result["reason"]
    assert flaws == []


def test_phrase_evidence_uses_confirmed_word_times_and_measured_errors():
    words = [
        SimpleNamespace(word=w, start=i * 0.4, end=i * 0.4 + 0.3)
        for i, w in enumerate(TEXT.split())
    ]
    result, flaws = compare_recognition(
        TEXT,
        TEXT,
        "We speak these words clearly to wrong wrong wrong wrong wrong wrong wrong",
        words,
    )
    assert result["available"] and result["score"] < 100
    assert flaws
    assert flaws[0]["start_time"] == words[6].start
    assert flaws[0]["end_time"] <= words[-1].end
    assert flaws[0]["confidence"] is None
    assert (
        flaws[0]["evidence"]["participant_value"]
        > flaws[0]["evidence"]["baseline_value"]
    )
