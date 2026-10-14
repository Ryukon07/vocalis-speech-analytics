import os
import subprocess
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app


def test_clean_migration_and_repeatable_seed(tmp_path):
    """Use the README's actual commands against a fresh database, without create_all."""
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path}/fresh.db",
        "STORAGE_ROOT": str(tmp_path / "audio"),
        "ENABLE_DEMO_MODE": "true",
        "ANALYSIS_PROVIDER": "mock",
        "MOCK_STAGE_DELAY": "0",
    }
    backend = Path(__file__).resolve().parents[1]
    for arguments in [("alembic", "upgrade", "head"), ("app.seed",), ("app.seed",)]:
        result = subprocess.run(
            [sys.executable, "-m", *arguments],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
    settings = Settings(
        database_url=env["DATABASE_URL"],
        storage_root=tmp_path / "audio",
        enable_demo_mode=True,
        analysis_provider="mock",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json()["provider_ready"]
        assert client.get("/api/v1/recordings").json()["total"] == 2
        assert client.get("/api/v1/datasets/groups").json()["total"] == 1
        history = client.get("/api/v1/analyses").json()
        assert history["total"] == 1 and history["items"][0]["status"] == "completed"
        result = client.get(
            "/api/v1/analyses/" + history["items"][0]["id"] + "/result"
        ).json()
        assert result["execution_mode"] == "mock" and result["feature_series"]
