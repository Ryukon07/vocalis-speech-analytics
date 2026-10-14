from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    String,
    Float,
    Integer,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now, onupdate=now)


class Recording(Identity, Base):
    __tablename__ = "recordings"
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transcript: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    speaker_id: Mapped[str] = mapped_column(String(255), default="")
    language: Mapped[str] = mapped_column(String(40), default="en")
    source_url: Mapped[str] = mapped_column(String(2048), default="")
    license: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    recording_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="participant", index=True)


class Reference(Identity, Base):
    __tablename__ = "references"
    title: Mapped[str] = mapped_column(String(255), index=True)
    recording_id: Mapped[str] = mapped_column(
        ForeignKey("recordings.id", ondelete="RESTRICT")
    )
    transcript: Mapped[str] = mapped_column(Text)
    speaker_id: Mapped[str] = mapped_column(String(255), default="")
    source_url: Mapped[str] = mapped_column(String(2048), default="")
    license: Mapped[str] = mapped_column(String(255), default="")
    eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Transcription(Identity, Base):
    __tablename__ = "transcriptions"
    recording_id: Mapped[str] = mapped_column(
        ForeignKey("recordings.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    transcript: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(40), default="en")
    model_name: Mapped[str] = mapped_column(String(100))
    error_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Rubric(Identity, Base):
    __tablename__ = "rubrics"
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    weights: Mapped[dict] = mapped_column(JSON)
    enabled_categories: Mapped[list] = mapped_column(JSON)


class Analysis(Identity, Base):
    __tablename__ = "analyses"
    participant_recording_id: Mapped[str] = mapped_column(
        ForeignKey("recordings.id", ondelete="RESTRICT")
    )
    reference_id: Mapped[str | None] = mapped_column(
        ForeignKey("references.id", ondelete="RESTRICT"), nullable=True
    )
    rubric_id: Mapped[str] = mapped_column(
        ForeignKey("rubrics.id", ondelete="RESTRICT")
    )
    rubric_snapshot: Mapped[dict] = mapped_column(JSON)
    transcript: Mapped[str] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(JSON)
    provider_name: Mapped[str] = mapped_column(String(100))
    provider_version: Mapped[str] = mapped_column(String(100))
    execution_mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress_stage: Mapped[str] = mapped_column(String(255), default="Queued")
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))


class FeatureSeries(Identity, Base):
    __tablename__ = "feature_series"
    __table_args__ = (UniqueConstraint("analysis_id", "feature_name"),)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    feature_name: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    window_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class DetectedFlaw(Identity, Base):
    __tablename__ = "detected_flaws"
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(100), index=True)
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    severity: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)


class ContrastiveGroup(Identity, Base):
    __tablename__ = "contrastive_groups"
    title: Mapped[str] = mapped_column(String(255))
    source_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    reference_recording_id: Mapped[str] = mapped_column(
        ForeignKey("recordings.id", ondelete="RESTRICT")
    )
    transcript: Mapped[str] = mapped_column(Text)
    transcript_version: Mapped[str] = mapped_column(String(100), default="1")
    speaker_id: Mapped[str] = mapped_column(String(255), default="")
    split: Mapped[str] = mapped_column(String(20), default="training")
    provenance: Mapped[str] = mapped_column(Text, default="")


class Variant(Identity, Base):
    __tablename__ = "variants"
    __table_args__ = (UniqueConstraint("group_id", "recording_id"),)
    group_id: Mapped[str] = mapped_column(
        ForeignKey("contrastive_groups.id", ondelete="CASCADE")
    )
    recording_id: Mapped[str] = mapped_column(
        ForeignKey("recordings.id", ondelete="RESTRICT")
    )
    level: Mapped[int] = mapped_column(Integer)
    flaw_labels: Mapped[list] = mapped_column(JSON)
    speaker_id: Mapped[str] = mapped_column(String(255), default="")
    provenance: Mapped[str] = mapped_column(Text, default="")


class Annotation(Identity, Base):
    __tablename__ = "annotations"
    recording_id: Mapped[str] = mapped_column(
        ForeignKey("recordings.id", ondelete="CASCADE"), index=True
    )
    flaw_type: Mapped[str] = mapped_column(String(100))
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    severity: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(100), default="human")
    notes: Mapped[str] = mapped_column(Text, default="")
