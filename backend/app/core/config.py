from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/vocalis.db"
    storage_root: Path = Path("./data/storage")
    analysis_provider: str = "evaluator"
    enable_demo_mode: bool = False
    max_upload_mb: int = Field(default=50, ge=1, le=500)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    job_timeout_seconds: int = Field(default=1800, ge=1)
    mock_stage_delay: float = Field(default=0.25, ge=0)
    app_version: str = "3.1.3"
    evaluator_device: Literal["cpu", "cuda"] = "cpu"
    evaluator_language: Literal["en"] = "en"
    asr_model: str = "base.en"
    transcription_model: str = "medium"
    transcription_fallback_model: str = "medium"
    model_cache_root: Path = Path("../model-artifacts")
    cpu_threads: int = Field(default=4, ge=1, le=32)
