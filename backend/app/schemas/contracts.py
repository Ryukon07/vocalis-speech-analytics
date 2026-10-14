from typing import Annotated, Literal, Generic, TypeVar
from uuid import UUID
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
    field_validator,
    HttpUrl,
)

Finite = Annotated[float, Field(allow_inf_nan=False)]
Nonnegative = Annotated[Finite, Field(ge=0)]
Score = Annotated[Finite, Field(ge=0, le=100)]
Confidence = Annotated[Finite, Field(ge=0, le=1)]
Category = Literal["pacing", "pitch", "energy", "pausing", "clarity"]
Mode = Literal["recording", "profile"]
Status = Literal["queued", "processing", "completed", "failed", "cancelled"]
DEFAULT_WEIGHTS = {
    "pacing": 25.0,
    "pitch": 20.0,
    "energy": 20.0,
    "pausing": 15.0,
    "clarity": 20.0,
}


class Contract(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", allow_inf_nan=False)


class RecordingPatch(Contract):
    title: str | None = Field(default=None, max_length=255)
    transcript: str | None = Field(default=None, max_length=200000)
    speaker_id: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, max_length=40)
    source_url: str | None = Field(default=None, max_length=2048)
    license: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=10000)
    recording_date: str | None = Field(default=None, max_length=40)
    category: Literal["participant", "reference", "variant", "demo"] | None = None

    @field_validator("source_url")
    @classmethod
    def url(cls, value):
        if value:
            return str(HttpUrl(value))
        return value

    @model_validator(mode="after")
    def no_null_text(self):
        for name in self.model_fields_set - {"recording_date"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class RecordingOut(Contract):
    id: str
    original_filename: str
    mime_type: str
    file_size: int
    duration_seconds: Nonnegative | None
    sample_rate: int | None
    channels: int | None
    transcript: str
    title: str
    speaker_id: str
    language: str
    source_url: str
    license: str
    notes: str
    recording_date: str | None
    category: str
    created_at: str
    updated_at: str


class ReferenceWrite(Contract):
    title: str = Field(min_length=1, max_length=255)
    recording_id: UUID
    transcript: str = Field(min_length=1, max_length=200000)
    speaker_id: str = Field(default="", max_length=255)
    source_url: str = Field(default="", max_length=2048)
    license: str = Field(default="", max_length=255)
    eligible: bool = True
    profile: dict | None = None
    _url = field_validator("source_url")(RecordingPatch.url.__func__)


class ReferenceOut(ReferenceWrite):
    id: str
    created_at: str
    updated_at: str


class RubricWrite(Contract):
    name: str = Field(min_length=1, max_length=255)
    weights: dict[Category, Nonnegative]
    enabled_categories: list[Category] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_weights(self):
        if len(set(self.enabled_categories)) != len(self.enabled_categories):
            raise ValueError("Duplicate rubric categories")
        if any(c not in self.weights for c in self.enabled_categories):
            raise ValueError("Every enabled category needs a weight")
        if abs(sum(self.weights[c] for c in self.enabled_categories) - 100) > 0.001:
            raise ValueError("Enabled category weights must sum to 100")
        return self


class RubricOut(RubricWrite):
    id: str
    version: int
    created_at: str
    updated_at: str


class AnalysisSettings(Contract):
    comparison_mode: Mode = "recording"
    enabled_categories: list[Category] = ["pacing", "pitch", "energy", "pausing"]
    sensitivity: Finite = Field(default=0.5, ge=0, le=1)
    window_seconds: Finite = Field(default=2, ge=0.1, le=60)
    overlap: Finite = Field(default=0.5, ge=0, lt=1)
    detailed_plots: bool = True

    @field_validator("enabled_categories")
    @classmethod
    def categories(cls, value):
        if not value or len(value) != len(set(value)):
            raise ValueError("Select unique enabled categories")
        return value


class AnalysisCreate(Contract):
    participant_recording_id: UUID
    reference_id: UUID | None = None
    rubric_id: UUID
    transcript: str = Field(default="", max_length=200000)
    transcript_mode: Literal["manual", "automatic"] = "manual"
    settings: AnalysisSettings = Field(default_factory=AnalysisSettings)


class TranscriptionOut(Contract):
    id: str
    recording_id: str
    status: Status
    transcript: str
    language: str
    model_name: str
    error_summary: str | None
    created_at: str
    updated_at: str


class AnalysisOut(Contract):
    id: str
    participant_recording_id: str
    participant_filename: str = ""
    reference_id: str | None
    reference_title: str = ""
    rubric_id: str
    rubric_snapshot: dict
    transcript: str
    settings: AnalysisSettings
    provider_name: str
    provider_version: str
    execution_mode: Literal["mock", "real"]
    status: Status
    progress_stage: str
    progress_percent: Score
    error_code: str | None
    error_summary: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    overall_score: Score | None
    flaw_count: int = 0


class Interval(Contract):
    start_seconds: Nonnegative
    end_seconds: Nonnegative

    @model_validator(mode="after")
    def ordered(self):
        if self.start_seconds > self.end_seconds:
            raise ValueError("Interval start must precede end")
        return self


class Evidence(Contract):
    baseline_value: Finite | None = None
    participant_value: Finite | None = None
    absolute_deviation: Finite | None = None
    difference_percent: Finite | None = None
    normalized_deviation: Finite | None = None
    units: str = ""
    measurement_name: str = ""
    source: Literal["measured", "mock"] = "measured"
    additional: dict[str, Finite | None] = Field(default_factory=dict)


class Flaw(Interval):
    id: str
    type: str = Field(min_length=1, max_length=100)
    category: Category
    severity: int = Field(ge=1, le=5)
    confidence: Confidence | None = None
    transcript_text: str | None = None
    evidence: Evidence = Field(default_factory=Evidence)
    interpretation_source: Literal["model", "rule", "generated", "mock"] = "rule"
    explanation: str = ""
    recommendation: str = ""


class Point(Contract):
    time_seconds: Nonnegative
    value: Finite | None


class Series(Contract):
    unit: str
    reference: list[Point] = Field(default_factory=list, max_length=100000)
    participant: list[Point] = Field(default_factory=list, max_length=100000)
    time_axis: Literal["recording", "participant_aligned"] = "recording"
    window_metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def sorted_times(self):
        for series in (self.reference, self.participant):
            if any(a.time_seconds > b.time_seconds for a, b in zip(series, series[1:])):
                raise ValueError("Feature timestamps must be ordered")
        return self


class Word(Interval):
    text: str
    confidence: Confidence | None = None


class Alignment(Contract):
    words: list[Word] = Field(default_factory=list)


class Scores(Contract):
    overall: Score | None = None
    dimensions: dict[Category, Score | None] = Field(default_factory=dict)


class RecognitionErrors(Contract):
    substitutions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    insertions: int = Field(ge=0)
    errors: int = Field(ge=0)
    word_error_rate: Nonnegative | None


class ClarityMeasurement(Contract):
    available: bool
    method: Literal["reference_relative_wer_v1"]
    model_name: str
    score: Score | None
    confirmed_word_count: int = Field(ge=0)
    minimum_word_count: int = Field(ge=1)
    maximum_reference_wer: Nonnegative
    reference_text: str
    participant_text: str
    reference: RecognitionErrors
    participant: RecognitionErrors
    excess_word_error_rate: Nonnegative | None
    reason: str | None

    @model_validator(mode="after")
    def availability(self):
        if self.available != (self.score is not None):
            raise ValueError("Clarity availability must match its score")
        for errors in (self.reference, self.participant):
            if (
                errors.errors
                != errors.substitutions + errors.deletions + errors.insertions
            ):
                raise ValueError("Recognition edit counts are inconsistent")
            if self.confirmed_word_count and (
                errors.word_error_rate is None
                or abs(
                    errors.word_error_rate - errors.errors / self.confirmed_word_count
                )
                > 0.00011
            ):
                raise ValueError("Recognition error rate does not match edit counts")
        if self.available:
            if (
                self.confirmed_word_count < self.minimum_word_count
                or self.reference.word_error_rate is None
                or self.reference.word_error_rate > self.maximum_reference_wer
            ):
                raise ValueError("The clarity baseline is insufficient")
            if (
                self.participant.word_error_rate is None
                or self.excess_word_error_rate is None
            ):
                raise ValueError("Available clarity requires recognition measurements")
            excess = max(
                0.0, self.participant.word_error_rate - self.reference.word_error_rate
            )
            if (
                abs(excess - self.excess_word_error_rate) > 0.00021
                or abs(self.score - round(100 * (1 - min(1.0, excess)), 1)) > 0.11
            ):
                raise ValueError("Clarity score does not match recognition evidence")
        return self


class AnalysisResult(Contract):
    analysis_id: str
    provider_name: str
    provider_version: str
    execution_mode: Literal["mock", "real"]
    status: Literal["completed"] = "completed"
    participant_duration_seconds: Nonnegative | None = None
    reference_duration_seconds: Nonnegative | None = None
    scores: Scores = Field(default_factory=Scores)
    flaws: list[Flaw] = Field(default_factory=list)
    feature_series: dict[str, Series] = Field(default_factory=dict)
    alignment: Alignment = Field(default_factory=Alignment)
    clarity: ClarityMeasurement | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def duration_bounds(self):
        if (
            self.clarity is not None
            and self.scores.dimensions.get("clarity") != self.clarity.score
        ):
            raise ValueError("Clarity evidence must match its dimension score")
        if len({f.id for f in self.flaws}) != len(self.flaws):
            raise ValueError("Duplicate flaw identifiers")
        for interval in [*self.flaws, *self.alignment.words]:
            if (
                self.participant_duration_seconds is None
                or interval.end_seconds > self.participant_duration_seconds + 0.001
            ):
                raise ValueError("Interval exceeds recording duration")
        for series in self.feature_series.values():
            for role in ["participant", "reference"]:
                duration = (
                    self.participant_duration_seconds
                    if role == "participant"
                    or series.time_axis == "participant_aligned"
                    else self.reference_duration_seconds
                )
                if duration is None and getattr(series, role):
                    raise ValueError(
                        "Feature timestamps require a known recording duration"
                    )
                if duration is not None and any(
                    p.time_seconds > duration + 0.001 for p in getattr(series, role)
                ):
                    raise ValueError("Feature timestamp exceeds recording duration")
        return self


class AnnotationWrite(Interval):
    recording_id: UUID
    flaw_type: str = Field(min_length=1, max_length=100)
    severity: int = Field(ge=1, le=5)
    source: str = Field(default="human", min_length=1, max_length=100)
    notes: str = Field(default="", max_length=10000)


class AnnotationOut(AnnotationWrite):
    id: str
    created_at: str
    updated_at: str


class GroupWrite(Contract):
    title: str = Field(min_length=1, max_length=255)
    source_id: str = Field(default="", max_length=100)
    reference_recording_id: UUID
    transcript: str = Field(min_length=1, max_length=200000)
    transcript_version: str = Field(default="1", max_length=100)
    speaker_id: str = Field(default="", max_length=255)
    split: Literal["training", "validation", "testing"] = "training"
    provenance: str = Field(default="", max_length=10000)


class VariantWrite(Contract):
    recording_id: UUID
    level: int = Field(ge=0, le=5)
    flaw_labels: list[str] = Field(default_factory=list)
    speaker_id: str = Field(default="", max_length=255)
    provenance: str = Field(default="", max_length=10000)


class VariantOut(VariantWrite):
    id: str
    group_id: str
    created_at: str
    updated_at: str


class GroupOut(GroupWrite):
    id: str
    created_at: str
    updated_at: str
    variants: list[VariantOut] = Field(default_factory=list)


T = TypeVar("T")


class Page(Contract, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int
