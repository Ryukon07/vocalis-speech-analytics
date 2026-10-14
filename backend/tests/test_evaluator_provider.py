"""Website contract and job integration checks; no model downloads or inference."""

from copy import deepcopy
import time
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import AppError
from app.ml import custom_provider as adapter
from app.ml.registry import get_provider
from app.ml.schemas import ProviderHealth, ProviderRequest
from app.schemas.contracts import AnalysisResult, AnalysisSettings, RubricOut
from app.workers.local_runner import JobStopped


REPORT = {
    "scores": {"pacing": 85.1, "intonation": 88.0, "energy": 95.0},
    "scoring_metadata": {
        "deductions": [
            {"flaw_type": "rushed_pacing", "points_deducted": 8.1},
            {"flaw_type": "awkward_pause", "points_deducted": 6.8},
        ]
    },
    "acoustic_statistics": {
        "candidate": {"duration_seconds": 3.0},
        "baseline": {"duration_seconds": 3.0},
    },
    "flaw_regions": [
        {
            "flaw_type": "awkward_pause",
            "start_time": 1.0,
            "end_time": 2.0,
            "severity": 3,
            "confidence": 0.8,
            "transcript_excerpt": "voice ... carries",
            "causal_explanation": "A one-second mid-phrase pause.",
            "recommendation": "Connect the phrase smoothly.",
            "evidence": {
                "baseline_value": None,
                "participant_value": 1.0,
                "absolute_deviation": None,
                "difference_percent": None,
                "normalized_deviation": None,
                "units": "seconds",
                "measurement_name": "pause_duration",
                "source": "candidate_threshold_only",
                "additional": {
                    "preceding_word": "voice",
                    "following_word": "carries",
                    "is_sentence_boundary": False,
                    "baseline_boundary_matched": False,
                },
            },
        }
    ],
    "time_series_data": {
        "candidate_pitch_timestamps": [0.0, 1.0, 3.0],
        "candidate_f0_semitones": [0.0, None, 2.0],
        "baseline_pitch_timestamps": [0.0, 0.75, 3.0],
        "baseline_f0_semitones": [0.0, 1.5, 2.0],
        "candidate_energy_timestamps": [0.0, 1.0, 3.0],
        "candidate_energy_db": [0.0, -4.0, 1.0],
        "baseline_energy_timestamps": [0.0, 0.75, 3.0],
        "baseline_energy_db": [0.0, -1.0, 1.0],
    },
    "word_alignments": {
        "candidate": [{"word": "clear", "start": 0.1, "end": 0.7, "confidence": 0.9}]
    },
    "warnings": [],
}


@pytest.fixture
def engine(monkeypatch):
    class FakeEngine:
        AlignmentError = type("AlignmentError", (Exception,), {})
        calls = []
        report = deepcopy(REPORT)

        @staticmethod
        def EvaluatorConfig():
            return SimpleNamespace(window_sec=2.0, window_step_sec=1.0)

        def evaluate(self, **kwargs):
            self.calls.append(kwargs)
            callback = kwargs.get("progress_callback")
            if callback:
                callback("Aligning participant words", 30)
            return deepcopy(self.report)

    fake = FakeEngine()
    monkeypatch.setattr(adapter, "_load_engine", lambda: fake)
    monkeypatch.setattr(
        adapter.CustomSpeechAnalysisProvider,
        "health_check",
        lambda self: ProviderHealth(ready=True, message="Test fixture engine"),
    )
    return fake


def provider_request(application, inputs):
    return ProviderRequest(
        job_id="test-job",
        participant_path="participant.wav",
        reference_path="reference.wav",
        transcript=inputs["transcript"],
        reference_transcript=inputs["transcript"],
        rubric=RubricOut(
            id="test-rubric",
            name="Balanced",
            version=1,
            created_at="now",
            updated_at="now",
            weights={
                "pacing": 25,
                "pitch": 20,
                "energy": 20,
                "pausing": 15,
                "clarity": 20,
            },
            enabled_categories=["pacing", "pitch", "energy", "pausing", "clarity"],
        ),
        settings=AnalysisSettings(window_seconds=4, overlap=0.25),
    )


def test_provider_maps_measured_report_and_rubric(application, inputs, engine):
    request = provider_request(application, inputs)
    result = adapter.CustomSpeechAnalysisProvider(Settings()).analyze(request)
    assert result.execution_mode == "real" and result.provider_name == "evaluator"
    assert result.scores.dimensions["clarity"] is None
    assert result.scores.dimensions["pacing"] == 91.9
    assert result.scores.dimensions["pausing"] == 93.2
    assert result.scores.overall == 91.94
    assert result.flaws[0].evidence.participant_value == 1.0
    assert "preceding_word" not in result.flaws[0].evidence.additional
    assert any("candidate-only" in warning for warning in result.warnings)
    assert result.feature_series["pitch"].reference[1].time_seconds == 0.75
    assert result.feature_series["pitch"].participant[1].value is None
    assert result.feature_series["pitch"].time_axis == "recording"
    assert engine.calls[0]["config"].window_sec == 4
    assert engine.calls[0]["config"].window_step_sec == 3


def test_disabled_categories_are_not_scored_or_returned(application, inputs, engine):
    request = provider_request(application, inputs)
    request.settings.enabled_categories = ["energy"]
    request.settings.detailed_plots = False
    result = adapter.CustomSpeechAnalysisProvider().analyze(request)
    assert result.scores.overall == 95
    assert result.scores.dimensions["pacing"] is None
    assert result.flaws == [] and result.feature_series == {}


def test_unavailable_pitch_is_excluded_from_overall(application, inputs, engine):
    engine.report["measurement_availability"] = {"pitch": False}
    result = adapter.CustomSpeechAnalysisProvider().analyze(
        provider_request(application, inputs)
    )
    assert result.scores.dimensions["pitch"] is None
    assert result.scores.overall == 93.26


def test_missing_reference_and_invalid_timestamps_fail(application, inputs, engine):
    request = provider_request(application, inputs)
    request.reference_path = None
    with pytest.raises(AppError, match="reference speech"):
        adapter.CustomSpeechAnalysisProvider().analyze(request)
    request.reference_path = "reference.wav"
    engine.report["flaw_regions"][0]["end_time"] = 5
    with pytest.raises(ValidationError, match="Interval exceeds recording duration"):
        adapter.CustomSpeechAnalysisProvider().analyze(request)


def test_alignment_failure_has_safe_actionable_message(application, inputs, engine):
    def fail(**kwargs):
        raise engine.AlignmentError("private/path.wav raw model error")

    engine.evaluate = fail
    with pytest.raises(AppError) as error:
        adapter.CustomSpeechAnalysisProvider().analyze(
            provider_request(application, inputs)
        )
    assert error.value.code == "ALIGNMENT_FAILED"
    assert "private/path" not in error.value.message


def test_cancellation_is_not_swallowed(application, inputs, engine):
    def stop(stage, percent):
        if percent == 30:
            raise JobStopped()

    with pytest.raises(JobStopped):
        adapter.CustomSpeechAnalysisProvider().analyze(
            provider_request(application, inputs), stop
        )


def test_website_job_calls_evaluator_and_persists_output(
    client, application, inputs, engine
):
    application.state.settings.analysis_provider = "evaluator"
    application.state.settings.enable_demo_mode = False
    caps = client.get("/api/v1/providers/capabilities").json()
    assert caps["execution_mode"] == "real" and "clarity" in caps["categories"]
    response = client.post("/api/v1/analyses", json=inputs)
    assert response.status_code == 202, response.text
    identifier = response.json()["id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/v1/analyses/{identifier}").json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(0.015)
    assert job["status"] == "completed", job
    result = AnalysisResult.model_validate(
        client.get(f"/api/v1/analyses/{identifier}/result").json()
    )
    assert result.scores.overall == 91.94 and result.flaws[0].type == "awkward_pause"
    assert engine.calls[0]["transcript"] == inputs["transcript"]
    assert engine.calls[0]["candidate_path"] != engine.calls[0]["baseline_path"]
    assert client.get(f"/api/v1/analyses/{identifier}/export/json").status_code == 200


def test_missing_dependencies_never_fall_back_to_demo(monkeypatch):
    monkeypatch.setattr(
        adapter, "DEPENDENCIES", ("vocalis_package_that_is_not_installed",)
    )
    with pytest.raises(AppError, match="Evaluator dependencies missing") as error:
        get_provider(Settings(analysis_provider="evaluator", enable_demo_mode=False))
    assert error.value.code == "PROVIDER_UNAVAILABLE"


def test_clarity_contributes_to_selected_rubric_and_retains_evidence(
    application, inputs, engine
):
    from clarity_analysis import compare_recognition

    text = "We speak these words clearly to share our ideas with everyone today"
    measurement, _ = compare_recognition(text, text, text.replace("today", "now"))
    engine.report["clarity"] = measurement
    engine.report["scores"]["clarity"] = measurement["score"]
    request = provider_request(application, inputs)
    request.settings.enabled_categories.append("clarity")
    result = adapter.CustomSpeechAnalysisProvider().analyze(request)
    assert result.clarity.available
    assert result.scores.dimensions["clarity"] == measurement["score"]
    expected = round(
        (25 * 91.9 + 20 * 88 + 20 * 95 + 15 * 93.2 + 20 * measurement["score"]) / 100, 2
    )
    assert result.scores.overall == expected
    request.settings.enabled_categories = ["energy"]
    result = adapter.CustomSpeechAnalysisProvider().analyze(request)
    assert result.clarity is None and result.scores.dimensions["clarity"] is None
    assert engine.calls[-1]["config"].enable_clarity is False
