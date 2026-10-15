import importlib.util
import json
import time
from pathlib import Path
from fastapi.testclient import TestClient
from app.models import Base
from app.repositories.database import database
from conftest import wav


def test_cloud_frontend_session_isolation_and_validation(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    (state / "seed-manifest.json").write_text(json.dumps({"protected_ids": []}))
    engine, _ = database("sqlite:///" + (state / "state.sqlite").as_posix())
    Base.metadata.create_all(engine)
    engine.dispose()
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><title>Vocalis cloud test</title>")
    (web / "assets/app.js").write_text("console.log('cloud-test')")
    monkeypatch.setenv("VOCALIS_PUBLIC_STATE", str(state))
    monkeypatch.setenv("VOCALIS_FRONTEND_DIST", str(web))
    monkeypatch.setenv("MODEL_CACHE_ROOT", str(tmp_path / "models"))
    monkeypatch.setenv("ANALYSIS_PROVIDER", "mock")
    monkeypatch.setenv("ENABLE_DEMO_MODE", "true")
    path = Path(__file__).resolve().parents[2] / "scripts/public_demo_api.py"
    spec = importlib.util.spec_from_file_location("public_cloud_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with TestClient(module.app, base_url="https://testserver") as owner:
        first = owner.get("/", headers={"x-forwarded-proto": "https"})
        assert first.status_code == 200 and "Vocalis cloud test" in first.text
        assert "Secure" in first.headers["set-cookie"]
        cookie = owner.cookies.get("vocalis-demo-session")
        assert owner.get("/history").status_code == 200
        assert owner.cookies.get("vocalis-demo-session") == cookie
        assert owner.get("/assets/app.js").status_code == 200
        assert owner.get("/missing.js").status_code == 404
        missing = owner.get("/api/v1/not-a-route")
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"

        def upload(name):
            response = owner.post("/api/v1/recordings", files={"file": (name, wav(), "audio/wav")})
            assert response.status_code == 201
            return response.json()

        participant = upload("private-visitor-a.wav")
        baseline = upload("visitor-a-reference.wav")
        text = "A clear voice carries a meaningful idea."
        reference = owner.post("/api/v1/references", json={"title": "Visitor A", "recording_id": baseline["id"], "transcript": text}).json()
        rubric = owner.post("/api/v1/rubrics", json={"name": "Visitor A rubric", "weights": {"pacing": 25, "pitch": 20, "energy": 20, "pausing": 15, "clarity": 20}, "enabled_categories": ["pacing", "pitch", "energy", "pausing", "clarity"]}).json()
        response = owner.post("/api/v1/analyses", json={"participant_recording_id": participant["id"], "reference_id": reference["id"], "rubric_id": rubric["id"], "transcript": text, "settings": {}})
        assert response.status_code == 202, response.text
        job = response.json()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if owner.get("/api/v1/analyses/" + job["id"]).json()["status"] == "completed": break
            time.sleep(0.02)
        assert owner.get("/api/v1/dashboard").json()["total"] == 1
        guest = TestClient(module.app, base_url="https://testserver")
        try:
            assert guest.get("/api/v1/recordings").json()["total"] == 0
            assert guest.get("/api/v1/analyses/" + job["id"]).status_code == 404
            dashboard = guest.get("/api/v1/dashboard").json()
            assert dashboard["total"] == 0 and dashboard["recent"] == []
            assert dashboard["references"] == 0 and dashboard["frequent_flaws"] == []
            assert "private-visitor-a.wav" not in json.dumps(dashboard)
        finally:
            guest.close()
        invalid = owner.post("/api/v1/references", json={"title": "Invalid", "recording_id": [], "transcript": text})
        assert invalid.status_code == 422
        group = owner.post("/api/v1/datasets/groups", json={"title": "Protected baseline group", "reference_recording_id": baseline["id"], "transcript": text}).json()
        module.protected.add(group["id"])
        assert owner.post(f"/api/v1/datasets/groups/{group['id']}/variants", json={"recording_id": participant["id"], "level": 1, "flaw_labels": []}).status_code == 403
