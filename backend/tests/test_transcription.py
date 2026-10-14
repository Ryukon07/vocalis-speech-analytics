import threading
import time
from types import SimpleNamespace
from app.ml.custom_provider import CustomSpeechAnalysisProvider
from app.ml.schemas import ProviderHealth
from app.workers import transcription_runner


def setup_engine(
    monkeypatch, application, text="A clear voice carries a meaningful idea."
):
    application.state.settings.analysis_provider = "evaluator"
    application.state.settings.transcription_model = "base.en"
    monkeypatch.setattr(
        CustomSpeechAnalysisProvider,
        "health_check",
        lambda self: ProviderHealth(ready=True, message="fixture"),
    )
    monkeypatch.setattr(
        transcription_runner,
        "_load_engine",
        lambda: SimpleNamespace(transcribe_audio=lambda *a, **kw: text),
    )


def wait_job(client, identifier):
    for _ in range(200):
        job = client.get(f"/api/v1/transcriptions/{identifier}").json()
        if job["status"] not in ["queued", "processing"]:
            return job
        time.sleep(0.01)
    raise AssertionError("Transcription did not complete")


def test_transcription_draft_does_not_overwrite_confirmed_text(
    client, application, inputs, monkeypatch
):
    setup_engine(monkeypatch, application)
    identifier = inputs["participant_recording_id"]
    client.patch(
        f"/api/v1/recordings/{identifier}", json={"transcript": "Already confirmed."}
    )
    response = client.post(f"/api/v1/recordings/{identifier}/transcriptions")
    assert response.status_code == 202
    job = wait_job(client, response.json()["id"])
    assert job["status"] == "completed" and job["transcript"] == inputs["transcript"]
    assert (
        client.get(f"/api/v1/recordings/{identifier}").json()["transcript"]
        == "Already confirmed."
    )
    assert client.post(f"/api/v1/transcriptions/{job['id']}/cancel").status_code == 409


def test_cancelled_transcription_discards_late_output(
    client, application, inputs, monkeypatch
):
    setup_engine(monkeypatch, application)
    started, release = threading.Event(), threading.Event()

    def transcribe(*a, **kw):
        started.set()
        assert release.wait(5)
        return "Late text"

    monkeypatch.setattr(
        transcription_runner,
        "_load_engine",
        lambda: SimpleNamespace(transcribe_audio=transcribe),
    )
    response = client.post(
        f"/api/v1/recordings/{inputs['participant_recording_id']}/transcriptions"
    )
    identifier = response.json()["id"]
    try:
        assert started.wait(3)
        duplicate = client.post(
            f"/api/v1/recordings/{inputs['participant_recording_id']}/transcriptions"
        ).json()
        assert duplicate["id"] == identifier
        assert (
            client.delete(
                f"/api/v1/recordings/{inputs['participant_recording_id']}"
            ).status_code
            == 409
        )
        assert (
            client.post(f"/api/v1/transcriptions/{identifier}/cancel").json()["status"]
            == "cancelled"
        )
    finally:
        release.set()
    time.sleep(0.05)
    assert client.get(f"/api/v1/transcriptions/{identifier}").json()["transcript"] == ""


def test_empty_transcription_fails_with_actionable_message(
    client, application, inputs, monkeypatch
):
    setup_engine(monkeypatch, application, "")
    response = client.post(
        f"/api/v1/recordings/{inputs['participant_recording_id']}/transcriptions"
    )
    job = wait_job(client, response.json()["id"])
    assert job["status"] == "failed" and "No speech" in job["error_summary"]


def test_mock_cannot_claim_real_transcription(client, inputs):
    response = client.post(
        f"/api/v1/recordings/{inputs['participant_recording_id']}/transcriptions"
    )
    assert response.status_code == 400


def test_draft_model_is_independent_from_frozen_clarity_model(
    client, application, inputs, monkeypatch
):
    setup_engine(monkeypatch, application)
    application.state.settings.transcription_model = "medium"
    application.state.settings.asr_model = "base.en"
    calls = []

    def transcribe(*args, model_name, **kwargs):
        calls.append(model_name)
        return inputs["transcript"]

    monkeypatch.setattr(transcription_runner, "_load_engine",
                        lambda: SimpleNamespace(transcribe_audio=transcribe))
    response = client.post(f"/api/v1/recordings/{inputs['participant_recording_id']}/transcriptions")
    job = wait_job(client, response.json()["id"])
    assert job["status"] == "completed" and job["model_name"] == "medium"
    assert calls == ["medium"]
    assert application.state.settings.asr_model == "base.en"


def test_unreliable_transcription_fails_without_persisting_hallucinated_draft(
    client, application, inputs, monkeypatch
):
    setup_engine(monkeypatch, application)

    class Unreliable(ValueError):
        code = "UNRELIABLE_TRANSCRIPT"

    def fail(*args, **kwargs):
        raise Unreliable("private diagnostic details")

    monkeypatch.setattr(
        transcription_runner,
        "_load_engine",
        lambda: SimpleNamespace(transcribe_audio=fail),
    )
    response = client.post(
        f"/api/v1/recordings/{inputs['participant_recording_id']}/transcriptions"
    )
    job = wait_job(client, response.json()["id"])
    assert job["status"] == "failed" and job["transcript"] == ""
    assert "unreliable repeated text" in job["error_summary"]
    assert "private" not in job["error_summary"]


def test_unreliable_primary_uses_fallback_and_records_actual_model(
    client, application, inputs, monkeypatch
):
    setup_engine(monkeypatch, application)
    calls = []

    class Unreliable(ValueError):
        code = "UNRELIABLE_TRANSCRIPT"

    def transcribe(*args, model_name, **kwargs):
        calls.append(model_name)
        if model_name == "base.en":
            raise Unreliable("private details")
        return inputs["transcript"]

    monkeypatch.setattr(transcription_runner, "_load_engine",
                        lambda: SimpleNamespace(transcribe_audio=transcribe))
    identifier = inputs["participant_recording_id"]
    response = client.post(f"/api/v1/recordings/{identifier}/transcriptions")
    job = wait_job(client, response.json()["id"])
    assert calls == ["base.en", "medium"]
    assert job["status"] == "completed" and job["model_name"] == "medium"
    assert job["transcript"] == inputs["transcript"]
    assert not job["error_summary"]
    assert client.get(f"/api/v1/recordings/{identifier}").json()["transcript"] == ""


def test_empty_primary_can_be_recovered_by_fallback(
    client, application, inputs, monkeypatch
):
    setup_engine(monkeypatch, application)
    def transcribe(*args, model_name, **kwargs):
        return "" if model_name == "base.en" else inputs["transcript"]
    monkeypatch.setattr(transcription_runner, "_load_engine",
                        lambda: SimpleNamespace(transcribe_audio=transcribe))
    response = client.post(f"/api/v1/recordings/{inputs['participant_recording_id']}/transcriptions")
    job = wait_job(client, response.json()["id"])
    assert job["status"] == "completed" and job["model_name"] == "medium"


def test_cancelled_fallback_discards_late_draft(
    client, application, inputs, monkeypatch
):
    setup_engine(monkeypatch, application)
    started, release = threading.Event(), threading.Event()
    def transcribe(*args, model_name, **kwargs):
        if model_name == "base.en":
            return ""
        started.set()
        assert release.wait(5)
        return "Late fallback text"
    monkeypatch.setattr(transcription_runner, "_load_engine",
                        lambda: SimpleNamespace(transcribe_audio=transcribe))
    response = client.post(f"/api/v1/recordings/{inputs['participant_recording_id']}/transcriptions")
    identifier = response.json()["id"]
    try:
        assert started.wait(3)
        client.post(f"/api/v1/transcriptions/{identifier}/cancel").raise_for_status()
    finally:
        release.set()
    time.sleep(0.05)
    job = client.get(f"/api/v1/transcriptions/{identifier}").json()
    assert job["status"] == "cancelled" and job["transcript"] == ""
    assert job["model_name"] == "base.en"


def test_model_availability_failure_does_not_trigger_quality_fallback(
    client, application, inputs, monkeypatch
):
    setup_engine(monkeypatch, application)
    calls = []
    def transcribe(*args, model_name, **kwargs):
        calls.append(model_name)
        raise RuntimeError("private model diagnostic")
    monkeypatch.setattr(transcription_runner, "_load_engine",
                        lambda: SimpleNamespace(transcribe_audio=transcribe))
    response = client.post(f"/api/v1/recordings/{inputs['participant_recording_id']}/transcriptions")
    job = wait_job(client, response.json()["id"])
    assert job["status"] == "failed" and calls == ["base.en"]
    assert "private" not in job["error_summary"]
