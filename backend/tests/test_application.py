import csv
import io
import time
from uuid import uuid4
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from app.schemas.contracts import AnalysisResult, Flaw, Series, Point, Scores
from app.ml.registry import PROVIDERS
from app.ml.mock_provider import MockSpeechAnalysisProvider
from app.models import Analysis, Recording, FeatureSeries
from conftest import wav


def wait(client, identifier, statuses=("completed", "failed", "cancelled"), timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get("/api/v1/analyses/" + identifier)
        assert response.status_code == 200, response.text
        job = response.json()
        if job["status"] in statuses:
            return job
        time.sleep(0.015)
    pytest.fail("Job did not reach a terminal state")


def test_health_capabilities_and_cors(client):
    assert client.get("/api/v1/health").json()["database"] == "ok"
    caps = client.get("/api/v1/providers/capabilities").json()
    assert caps["execution_mode"] == "mock" and not caps["automatic_transcription"]
    response = client.options(
        "/api/v1/recordings",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_upload_metadata_audio_range_and_cleanup(client, application):
    response = client.post(
        "/api/v1/recordings",
        files={"file": ("../../untrusted.wav", wav(), "audio/wav")},
    )
    assert response.status_code == 201
    recording = response.json()
    assert (
        recording["duration_seconds"] == 3
        and recording["original_filename"] == "untrusted.wav"
    )
    assert "storage_key" not in recording
    assert (
        client.get("/api/v1/recordings/" + recording["id"]).json()["sample_rate"]
        == 16000
    )
    audio = client.get(
        f"/api/v1/recordings/{recording['id']}/audio", headers={"Range": "bytes=0-43"}
    )
    assert audio.status_code == 206 and audio.content[:4] == b"RIFF"
    assert (
        client.patch(
            "/api/v1/recordings/" + recording["id"], json={"speaker_id": "anonymous"}
        ).status_code
        == 200
    )
    with application.state.sessions() as db:
        key = db.get(Recording, recording["id"]).storage_key
    assert application.state.storage.path(key).exists()
    assert client.delete("/api/v1/recordings/" + recording["id"]).status_code == 204
    assert not application.state.storage.path(key).exists()
    assert client.get("/api/v1/recordings/" + recording["id"]).status_code == 404


@pytest.mark.parametrize(
    "name,mime,payload",
    [
        ("bad.txt", "text/plain", b"hello"),
        ("fake.wav", "audio/wav", b"<html>bad</html>"),
        ("good.wav", "text/html", wav()),
        ("empty.mp3", "audio/mpeg", b""),
    ],
    ids=["extension", "header", "mime", "empty"],
)
def test_invalid_uploads(client, name, mime, payload):
    assert (
        client.post(
            "/api/v1/recordings", files={"file": (name, payload, mime)}
        ).status_code
        == 415
    )


def test_limit_and_no_partial_file(client, application):
    application.state.settings.max_upload_mb = 1
    response = client.post(
        "/api/v1/recordings", files={"file": ("large.wav", wav(40), "audio/wav")}
    )
    assert response.status_code == 413
    assert not list(application.state.storage.root.iterdir())


def test_analysis_transitions_exports_and_delete(client, application, inputs):
    assert client.get("/api/v1/references/" + inputs["reference_id"]).json()["eligible"]
    response = client.post(
        "/api/v1/analyses", json=inputs, headers={"Idempotency-Key": "test-once"}
    )
    assert response.status_code == 202
    initial = response.json()
    assert initial["status"] == "queued"
    identifier = initial["id"]
    states = set()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get("/api/v1/analyses/" + identifier).json()
        states.add(job["status"])
        if job["status"] == "completed":
            break
        time.sleep(0.01)
    assert "processing" in states and "completed" in states
    result = client.get(f"/api/v1/analyses/{identifier}/result")
    assert result.status_code == 200, result.text
    payload = result.json()
    validated = AnalysisResult.model_validate(payload)
    assert validated.execution_mode == "mock" and validated.flaws
    assert all(f.end_seconds <= 3 for f in validated.flaws)
    assert all(f.evidence.source == "mock" for f in validated.flaws)
    assert client.get(f"/api/v1/analyses/{identifier}/export/json").json() == payload
    rows = list(
        csv.DictReader(
            io.StringIO(client.get(f"/api/v1/analyses/{identifier}/export/csv").text)
        )
    )
    assert len(rows) == len(validated.flaws) and rows[0]["execution_mode"] == "mock"
    assert (
        client.delete(
            "/api/v1/recordings/" + inputs["participant_recording_id"]
        ).status_code
        == 409
    )
    with application.state.sessions() as db:
        keys = [
            r.storage_key
            for r in db.scalars(
                select(FeatureSeries).where(FeatureSeries.analysis_id == identifier)
            )
        ]
    assert keys
    assert client.delete("/api/v1/analyses/" + identifier).status_code == 204
    assert all(not application.state.storage.path(k).exists() for k in keys)
    assert (
        client.delete(
            "/api/v1/recordings/" + inputs["participant_recording_id"]
        ).status_code
        == 204
    )


def test_idempotency_and_mismatch(client, inputs):
    first = client.post(
        "/api/v1/analyses", json=inputs, headers={"Idempotency-Key": "unique"}
    ).json()
    again = client.post(
        "/api/v1/analyses", json=inputs, headers={"Idempotency-Key": "unique"}
    ).json()
    assert first["id"] == again["id"]
    changed = {**inputs, "transcript": "Changed words"}
    assert (
        client.post(
            "/api/v1/analyses", json=changed, headers={"Idempotency-Key": "unique"}
        ).status_code
        == 409
    )
    assert client.get("/api/v1/analyses").json()["total"] == 1
    assert (
        client.post("/api/v1/analyses", json=changed).json()["error"]["code"]
        == "TRANSCRIPT_MISMATCH"
    )


def test_invalid_inputs_and_provider_unavailable(client, application, inputs):
    assert (
        client.post(
            "/api/v1/analyses",
            json={**inputs, "participant_recording_id": str(uuid4())},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/analyses", json={**inputs, "participant_recording_id": "invalid"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/analyses", json={**inputs, "transcript_mode": "automatic"}
        ).json()["error"]["code"]
        == "UNSUPPORTED_INPUT"
    )
    assert (
        client.post("/api/v1/analyses", json={**inputs, "transcript": ""}).json()[
            "error"
        ]["code"]
        == "TRANSCRIPT_REQUIRED"
    )
    application.state.settings.enable_demo_mode = False
    assert client.post("/api/v1/analyses", json=inputs).status_code == 503
    assert not client.get("/api/v1/providers").json()["ready"]
    assert not client.get("/api/v1/health").json()["provider_ready"]
    assert client.get("/api/v1/providers/capabilities").status_code == 503


def test_dataset_and_annotation_bounds(client, inputs):
    recording = inputs["participant_recording_id"]
    group = client.post(
        "/api/v1/datasets/groups",
        json={
            "title": "Contrastive test",
            "reference_recording_id": recording,
            "transcript": inputs["transcript"],
        },
    ).json()
    another = client.post(
        "/api/v1/recordings", files={"file": ("variant.wav", wav(), "audio/wav")}
    ).json()
    variant = client.post(
        f"/api/v1/datasets/groups/{group['id']}/variants",
        json={"recording_id": another["id"], "level": 3, "flaw_labels": ["pacing"]},
    )
    assert variant.status_code == 201
    assert (
        client.get("/api/v1/datasets/groups/" + group["id"]).json()["variants"][0][
            "level"
        ]
        == 3
    )
    assert (
        client.post(
            "/api/v1/datasets/groups",
            json={
                "title": "Leak",
                "reference_recording_id": recording,
                "transcript": "Same",
                "split": "testing",
            },
        ).status_code
        == 409
    )
    base = {
        "recording_id": another["id"],
        "flaw_type": "excessive_pace",
        "severity": 3,
        "start_seconds": 1,
        "end_seconds": 2,
    }
    annotation = client.post("/api/v1/datasets/annotations", json=base)
    assert annotation.status_code == 201
    assert (
        client.post(
            "/api/v1/datasets/annotations", json={**base, "end_seconds": 4}
        ).json()["error"]["code"]
        == "INTERVAL_OUT_OF_BOUNDS"
    )
    assert (
        client.post(
            "/api/v1/datasets/annotations", json={**base, "start_seconds": 2.5}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/datasets/annotations/" + annotation.json()["id"],
            json={**base, "notes": "Human checked"},
        ).status_code
        == 200
    )
    assert (
        client.delete(
            "/api/v1/datasets/annotations/" + annotation.json()["id"]
        ).status_code
        == 204
    )
    assert client.delete("/api/v1/recordings/" + another["id"]).status_code == 409
    assert client.delete("/api/v1/datasets/groups/" + group["id"]).status_code == 204
    assert client.delete("/api/v1/recordings/" + another["id"]).status_code == 204


@pytest.mark.parametrize(
    "weights,enabled",
    [
        ({"pacing": 90}, ["pacing"]),
        ({"pacing": 100}, ["pacing", "pitch"]),
        ({"pacing": 100}, ["pacing", "pacing"]),
        ({"pacing": -1, "pitch": 101}, ["pacing", "pitch"]),
    ],
)
def test_rubric_validation(client, weights, enabled):
    assert (
        client.post(
            "/api/v1/rubrics",
            json={"name": "Invalid", "weights": weights, "enabled_categories": enabled},
        ).status_code
        == 422
    )


def test_rubric_snapshots_and_real_only_dashboard(client, inputs):
    identifier = client.post("/api/v1/analyses", json=inputs).json()["id"]
    wait(client, identifier)
    response = client.patch(
        "/api/v1/rubrics/" + inputs["rubric_id"],
        json={
            "name": "New weights",
            "weights": {"pacing": 100},
            "enabled_categories": ["pacing"],
        },
    )
    assert response.json()["version"] == 2
    assert (
        client.get("/api/v1/analyses/" + identifier).json()["rubric_snapshot"][
            "version"
        ]
        == 1
    )
    dashboard = client.get("/api/v1/dashboard").json()
    assert (
        dashboard["completed"] == 1
        and dashboard["average_score"] is None
        and not dashboard["frequent_flaws"]
    )


def test_cancellation_discards_late_output(client, application, inputs):
    application.state.settings.mock_stage_delay = 0.15
    identifier = client.post("/api/v1/analyses", json=inputs).json()["id"]
    wait(client, identifier, ("processing",))
    assert (
        client.post("/api/v1/analyses/" + identifier + "/cancel").json()["status"]
        == "cancelled"
    )
    time.sleep(0.3)
    assert client.get("/api/v1/analyses/" + identifier).json()["status"] == "cancelled"
    assert client.get("/api/v1/analyses/" + identifier + "/result").status_code == 409


def test_failure_retry_and_timeout(client, application, inputs, monkeypatch):
    class Broken(MockSpeechAnalysisProvider):
        fail = True

        def analyze(self, request, progress_callback=None):
            if self.fail:
                raise RuntimeError("Private provider detail")
            return super().analyze(request, progress_callback)

    monkeypatch.setitem(PROVIDERS, "mock", Broken)
    identifier = client.post("/api/v1/analyses", json=inputs).json()["id"]
    job = wait(client, identifier)
    assert (
        job["status"] == "failed"
        and "Private provider detail" not in job["error_summary"]
    )
    Broken.fail = False
    assert client.post("/api/v1/analyses/" + identifier + "/retry").status_code == 202
    assert wait(client, identifier)["status"] == "completed"
    assert client.post("/api/v1/analyses/" + identifier + "/retry").status_code == 409

    class Slow(MockSpeechAnalysisProvider):
        def analyze(self, request, progress_callback=None):
            time.sleep(1.5)
            return super().analyze(request, progress_callback)

    monkeypatch.setitem(PROVIDERS, "mock", Slow)
    application.state.settings.job_timeout_seconds = 1
    timeout = client.post("/api/v1/analyses", json=inputs).json()["id"]
    assert wait(client, timeout)["error_code"] == "JOB_TIMEOUT"
    time.sleep(0.7)
    assert client.get("/api/v1/analyses/" + timeout).json()["status"] == "failed"


def test_startup_recovers_interrupted_job(application, inputs, client):
    identifier = client.post("/api/v1/analyses", json=inputs).json()["id"]
    wait(client, identifier)
    with application.state.sessions() as db:
        job = db.get(Analysis, identifier)
        job.status = "processing"
        db.commit()
    from app.workers.local_runner import LocalRunner

    runner = LocalRunner(
        application.state.sessions,
        application.state.storage,
        application.state.settings,
    )
    try:
        assert (
            client.get("/api/v1/analyses/" + identifier).json()["error_code"]
            == "RUNNER_RESTARTED"
        )
    finally:
        runner.shutdown()


def test_schema_validation():
    with pytest.raises(ValidationError):
        Scores(overall=float("nan"))
    with pytest.raises(ValidationError):
        Point(time_seconds=0, value=float("inf"))
    with pytest.raises(ValidationError):
        Flaw(
            id="x",
            type="pace",
            category="pacing",
            start_seconds=2,
            end_seconds=1,
            severity=3,
        )
    with pytest.raises(ValidationError):
        Flaw(
            id="x",
            type="pace",
            category="pacing",
            start_seconds=0,
            end_seconds=1,
            severity=3,
            confidence=1.1,
        )
    with pytest.raises(ValidationError):
        Series(
            unit="Hz",
            participant=[
                Point(time_seconds=2, value=3),
                Point(time_seconds=1, value=4),
            ],
        )
    with pytest.raises(ValidationError):
        AnalysisResult(
            analysis_id="x",
            provider_name="mock",
            provider_version="1",
            execution_mode="mock",
            participant_duration_seconds=1,
            flaws=[
                Flaw(
                    id="x",
                    type="pace",
                    category="pacing",
                    start_seconds=0,
                    end_seconds=2,
                    severity=3,
                )
            ],
        )


def test_storage_path_validation(application):
    from app.core.exceptions import AppError

    with pytest.raises(AppError):
        application.state.storage.path("../private.env")


def test_provider_reproducibility(client, application, inputs):
    identifier = client.post("/api/v1/analyses", json=inputs).json()["id"]
    wait(client, identifier)
    first = client.get("/api/v1/analyses/" + identifier + "/result").json()
    second = client.post("/api/v1/analyses", json=inputs).json()["id"]
    wait(client, second)
    result = client.get("/api/v1/analyses/" + second + "/result").json()
    assert (
        first["feature_series"] == result["feature_series"]
        and first["scores"] == result["scores"]
    )
    assert [f["evidence"] for f in first["flaws"]] == [
        f["evidence"] for f in result["flaws"]
    ]


def test_pagination_and_new_features(client, inputs):
    assert client.get("/api/v1/recordings?limit=1").json()["total"] == 2
    assert len(client.get("/api/v1/recordings?limit=1").json()["items"]) == 1
    assert client.get("/api/v1/recordings?limit=0").status_code == 422
    assert client.get("/api/v1/analyses?offset=-1").status_code == 422
    result = AnalysisResult(
        analysis_id="id",
        provider_name="custom",
        provider_version="1",
        execution_mode="real",
        participant_duration_seconds=2,
        feature_series={
            "new_feature": Series(
                unit="custom", participant=[Point(time_seconds=1, value=None)]
            )
        },
    )
    assert result.feature_series["new_feature"].participant[0].value is None


def test_unknown_compressed_duration_is_unavailable(client, inputs):
    recording = client.post(
        "/api/v1/recordings",
        files={"file": ("unprocessed.mp3", b"ID3" + b"\0" * 100, "audio/mpeg")},
    )
    assert recording.status_code == 201 and recording.json()["duration_seconds"] is None
    identifier = client.post(
        "/api/v1/analyses",
        json={**inputs, "participant_recording_id": recording.json()["id"]},
    ).json()["id"]
    assert wait(client, identifier)["status"] == "completed"
    result = client.get("/api/v1/analyses/" + identifier + "/result").json()
    assert result["participant_duration_seconds"] is None
    assert (
        result["scores"]["overall"] is None
        and not result["feature_series"]
        and not result["flaws"]
    )


def test_cross_role_dataset_split_isolation(client, inputs):
    reference = client.get("/api/v1/references/" + inputs["reference_id"]).json()[
        "recording_id"
    ]
    first = client.post(
        "/api/v1/datasets/groups",
        json={
            "title": "Training",
            "reference_recording_id": reference,
            "transcript": inputs["transcript"],
            "split": "training",
        },
    ).json()
    assert (
        client.post(
            "/api/v1/datasets/groups/" + first["id"] + "/variants",
            json={"recording_id": inputs["participant_recording_id"], "level": 1},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/datasets/groups",
            json={
                "title": "Leaked source",
                "reference_recording_id": inputs["participant_recording_id"],
                "transcript": inputs["transcript"],
                "split": "testing",
            },
        ).status_code
        == 409
    )

    third = client.post(
        "/api/v1/recordings", files={"file": ("testing.wav", wav(), "audio/wav")}
    ).json()
    group = client.post(
        "/api/v1/datasets/groups",
        json={
            "title": "Testing",
            "reference_recording_id": third["id"],
            "transcript": inputs["transcript"],
            "split": "testing",
        },
    ).json()
    assert (
        client.post(
            "/api/v1/datasets/groups/" + group["id"] + "/variants",
            json={"recording_id": reference, "level": 2},
        ).status_code
        == 409
    )


def test_used_reference_keeps_analysis_inputs_stable(client, inputs):
    identifier = client.post("/api/v1/analyses", json=inputs).json()["id"]
    wait(client, identifier)
    reference = client.get("/api/v1/references/" + inputs["reference_id"]).json()
    editable = {
        k: reference[k]
        for k in [
            "title",
            "recording_id",
            "transcript",
            "speaker_id",
            "source_url",
            "license",
            "eligible",
            "profile",
        ]
    }
    assert (
        client.patch(
            "/api/v1/references/" + inputs["reference_id"],
            json={**editable, "title": "Updated metadata"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            "/api/v1/references/" + inputs["reference_id"],
            json={**editable, "transcript": "Different text"},
        ).status_code
        == 409
    )
