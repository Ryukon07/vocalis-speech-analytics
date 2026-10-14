"""Deterministic measurement checks; no model downloads or synthetic model claims."""

import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

np = pytest.importorskip("numpy")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from delivery_analysis import detect_delivery_flaws, mapped_feature
from speech_runtime import alignment_spelling
from evaluator import EvaluatorConfig, EvidenceData, FlawRegion, compute_rubric_scores
from evaluator import sanitize_for_json


def features(words):
    end = words[-1].end + 0.1
    times = np.arange(0, end, 0.016)
    return SimpleNamespace(
        words=words,
        pitch_times=times,
        energy_times=times,
        f0_centered_st=np.zeros(len(times)),
        energy_db_relative=np.zeros(len(times)),
    )


def words():
    return [
        SimpleNamespace(word=f"word{chr(97+i)}", start=i * 0.4 + 0.1, end=i * 0.4 + 0.4)
        for i in range(20)
    ]


def test_pacing_is_localized_and_does_not_treat_a_pause_as_rushing():
    baseline = words()
    a, b = baseline[4].start, baseline[9].end

    def warp(t):
        return (
            t if t <= a else a + (t - a) / 1.8 if t < b else t - (b - a) * (1 - 1 / 1.8)
        )

    candidate = [
        SimpleNamespace(word=w.word, start=warp(w.start), end=warp(w.end))
        for w in baseline
    ]
    flaws, _ = detect_delivery_flaws(
        features(baseline), features(candidate), EvaluatorConfig()
    )
    pacing = [f for f in flaws if f["flaw_type"] == "rushed_pacing"]
    assert len(pacing) == 1
    assert pacing[0]["start_time"] > 0
    assert pacing[0]["end_time"] < candidate[-1].end
    # Pacing evidence is recomputed after overlapping phrase regions are merged.
    evidence = pacing[0]["evidence"]
    assert evidence["participant_value"] > evidence["baseline_value"] * 1.3
    assert pacing[0]["measured_value"] == evidence["participant_value"]


def test_repeated_word_pause_uses_corresponding_sequence_boundary():
    baseline = words()
    for w in baseline:
        w.word = "the"
    position = baseline[6].end + 0.03
    candidate = [
        SimpleNamespace(
            word=w.word,
            start=w.start + (2.2 if w.start > position else 0),
            end=w.end + (2.2 if w.end > position else 0),
        )
        for w in baseline
    ]
    flaws, _ = detect_delivery_flaws(
        features(baseline), features(candidate), EvaluatorConfig()
    )
    pauses = [f for f in flaws if f["flaw_type"] == "awkward_pause"]
    assert len(pauses) == 1
    assert pauses[0]["evidence"]["additional"]["baseline_boundary_matched"] == 1
    assert abs(pauses[0]["evidence"]["baseline_value"] - 0.1) < 0.001
    assert not any(f["flaw_type"] in ["rushed_pacing", "slow_pacing"] for f in flaws)


def test_unvoiced_and_outside_alignment_values_remain_unavailable():
    baseline = features(words())
    candidate = features(words())
    baseline.f0_centered_st[15:25] = np.nan
    times, mapped = mapped_feature(baseline, candidate, "pitch")
    assert np.isnan(mapped[times < candidate.words[0].start]).all()
    assert np.isnan(mapped[15:25]).any()


def test_severe_rushing_does_not_get_a_smaller_penalty_because_it_is_shorter():
    def flaw(severity, end):
        return FlawRegion(
            "rushed_pacing",
            1,
            end,
            severity,
            None,
            "",
            "",
            EvidenceData(additional={"reference_region_seconds": 4}),
        )

    mild, _ = compute_rubric_scores([flaw(2, 4)], duration=20)
    severe, _ = compute_rubric_scores([flaw(5, 3)], duration=20)
    assert severe["pacing"] < mild["pacing"]


def test_numbers_and_accents_have_supported_alignment_spelling():
    assert alignment_spelling("19") == "NINETEEN"
    assert alignment_spelling("34th") == "THIRTY|FOURTH"
    assert alignment_spelling("naïve") == "NAIVE"


def test_measurement_availability_remains_boolean_after_json_sanitization():
    report = sanitize_for_json(
        {"pitch": False, "clarity": np.bool_(True), "score": np.float64(92)}
    )
    assert report["pitch"] is False
    assert report["clarity"] is True
    assert report["score"] == 92
