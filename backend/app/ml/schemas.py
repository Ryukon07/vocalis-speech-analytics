from pathlib import Path
from typing import Literal
from pydantic import Field
from app.schemas.contracts import (
    Contract,
    AnalysisSettings,
    RubricOut,
    Word,
    Category,
    Mode,
    Nonnegative,
)


class Capabilities(Contract):
    provider_name: str
    provider_version: str
    execution_mode: Literal["mock", "real"]
    ready: bool
    requires_transcript: bool = True
    requires_reference: bool = True
    automatic_transcription: bool = False
    comparison_modes: list[Mode] = ["recording"]
    categories: list[Category] = ["pacing", "pitch", "energy", "pausing", "clarity"]
    supports_windows: bool = True
    supports_cancellation: bool = True
    message: str = ""


class ProviderHealth(Contract):
    ready: bool
    message: str


class ProviderRequest(Contract):
    job_id: str
    participant_path: Path  # Resolved internally, never accepted by the public API.
    participant_duration_seconds: Nonnegative | None = None
    reference_path: Path | None = None
    reference_duration_seconds: Nonnegative | None = None
    reference_profile: dict | None = None
    transcript: str
    reference_transcript: str = ""
    rubric: RubricOut
    settings: AnalysisSettings
    alignment: list[Word] = Field(default_factory=list)
    dataset_metadata: dict = Field(default_factory=dict)
