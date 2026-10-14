import io
import wave
import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.models import Base


def wav(seconds=3):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as writer:
        writer.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        writer.writeframes(b"\0\0" * int(seconds * 16000))
    return stream.getvalue()


@pytest.fixture
def application(tmp_path):
    config = Settings(
        database_url=f"sqlite:///{tmp_path}/test.db",
        storage_root=tmp_path / "storage",
        analysis_provider="mock",
        enable_demo_mode=True,
        mock_stage_delay=0.01,
    )
    app = create_app(config)
    Base.metadata.create_all(app.state.engine)
    return app


@pytest.fixture
def client(application):
    with TestClient(application) as client:
        yield client


@pytest.fixture
def inputs(client):
    participant = client.post(
        "/api/v1/recordings", files={"file": ("participant.wav", wav(), "audio/wav")}
    ).json()
    baseline = client.post(
        "/api/v1/recordings", files={"file": ("baseline.wav", wav(), "audio/wav")}
    ).json()
    text = "A clear voice carries a meaningful idea."
    reference = client.post(
        "/api/v1/references",
        json={
            "title": "Test baseline",
            "recording_id": baseline["id"],
            "transcript": text,
        },
    ).json()
    rubric = client.post(
        "/api/v1/rubrics",
        json={
            "name": "Test rubric",
            "weights": {
                "pacing": 25,
                "pitch": 20,
                "energy": 20,
                "pausing": 15,
                "clarity": 20,
            },
            "enabled_categories": ["pacing", "pitch", "energy", "pausing", "clarity"],
        },
    ).json()
    return {
        "participant_recording_id": participant["id"],
        "reference_id": reference["id"],
        "rubric_id": rubric["id"],
        "transcript": text,
    }
