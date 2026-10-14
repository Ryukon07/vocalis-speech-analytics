import hashlib
import json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.exceptions import AppError
from app.models import (
    Analysis,
    Recording,
    Reference,
    Rubric,
    FeatureSeries,
    DetectedFlaw,
)
from app.repositories.database import get
from app.schemas.contracts import AnalysisOut, AnalysisResult, RubricOut


def analysis_out(session, row):
    value = AnalysisOut.model_validate(row)
    value.participant_filename = get(
        session, Recording, row.participant_recording_id
    ).original_filename
    value.reference_title = (
        get(session, Reference, row.reference_id).title if row.reference_id else ""
    )
    value.flaw_count = len((row.result_summary or {}).get("flaws", []))
    return value


def create_analysis(session, request, provider, key):
    request_hash = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
    previous = session.scalar(select(Analysis).where(Analysis.idempotency_key == key))
    if previous:
        if previous.request_hash != request_hash:
            raise AppError(
                "IDEMPOTENCY_CONFLICT",
                "This submission key belongs to different inputs.",
                409,
            )
        return previous, False
    participant = get(session, Recording, request.participant_recording_id)
    rubric = get(session, Rubric, request.rubric_id)
    reference = (
        get(session, Reference, request.reference_id) if request.reference_id else None
    )
    caps = provider.get_capabilities()
    if caps.execution_mode == "real":
        targets = [participant]
        if reference:
            targets.append(get(session, Recording, reference.recording_id))
        if any(
            r.duration_seconds is not None and not 0.5 <= r.duration_seconds <= 180
            for r in targets
        ):
            raise AppError(
                "AUDIO_DURATION",
                "Choose reference and participant speech excerpts between half a second and three minutes.",
            )
        if request.settings.window_seconds < 0.5:
            raise AppError(
                "INVALID_WINDOW",
                "Real acoustic comparisons need a window of at least half a second.",
            )
    if request.transcript_mode == "automatic" and not caps.automatic_transcription:
        raise AppError(
            "UNSUPPORTED_INPUT",
            "Automatic transcription is not available with this provider.",
        )
    if (
        caps.requires_transcript
        and request.transcript_mode == "manual"
        and not request.transcript.strip()
    ):
        raise AppError(
            "TRANSCRIPT_REQUIRED", "Provide a transcript for this analysis provider."
        )
    if request.settings.comparison_mode not in caps.comparison_modes:
        raise AppError(
            "UNSUPPORTED_MODE", "This comparison mode is not supported by the provider."
        )
    if (caps.requires_reference and not reference) or (
        reference and not reference.eligible
    ):
        raise AppError("REFERENCE_REQUIRED", "Select an eligible reference.")
    if request.settings.comparison_mode == "profile" and (
        not reference or not reference.profile
    ):
        raise AppError(
            "PROFILE_REQUIRED", "Select a reference with a processed profile."
        )
    if (
        request.settings.comparison_mode == "recording"
        and reference
        and request.transcript_mode == "manual"
        and request.transcript.strip().split() != reference.transcript.strip().split()
    ):
        raise AppError(
            "TRANSCRIPT_MISMATCH",
            "Recording comparison requires the same transcript as the reference.",
        )
    categories = request.settings.enabled_categories
    if not set(categories) <= set(caps.categories) or not set(categories) <= set(
        rubric.enabled_categories
    ):
        raise AppError(
            "UNSUPPORTED_CATEGORY",
            "Selected categories are not supported by both rubric and provider.",
        )
    if sum(rubric.weights[c] for c in categories) <= 0:
        raise AppError(
            "INVALID_RUBRIC", "Enabled categories need a positive total weight."
        )
    row = Analysis(
        participant_recording_id=participant.id,
        reference_id=reference.id if reference else None,
        rubric_id=rubric.id,
        rubric_snapshot=RubricOut.model_validate(rubric).model_dump(mode="json"),
        transcript=request.transcript,
        settings=request.settings.model_dump(),
        provider_name=caps.provider_name,
        provider_version=caps.provider_version,
        execution_mode=caps.execution_mode,
        idempotency_key=key,
        request_hash=request_hash,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        previous = session.scalar(
            select(Analysis).where(Analysis.idempotency_key == key)
        )
        if previous and previous.request_hash == request_hash:
            return previous, False
        raise AppError(
            "IDEMPOTENCY_CONFLICT",
            "This submission key belongs to different inputs.",
            409,
        )
    return row, True


def persist_result(session, storage, job, result):
    if (
        result.analysis_id != job.id
        or result.provider_name != job.provider_name
        or result.provider_version != job.provider_version
        or result.execution_mode != job.execution_mode
    ):
        raise AppError(
            "INVALID_PROVIDER_RESULT", "Provider returned inconsistent job metadata."
        )
    recording = get(session, Recording, job.participant_recording_id)
    if recording.duration_seconds is not None and (
        result.participant_duration_seconds is None
        or abs(result.participant_duration_seconds - recording.duration_seconds) > 0.01
    ):
        raise AppError(
            "INVALID_PROVIDER_RESULT",
            "Provider returned inconsistent recording duration.",
        )
    available = {
        c: s
        for c, s in result.scores.dimensions.items()
        if s is not None and c in job.settings["enabled_categories"]
    }
    if result.scores.overall is not None:
        if not available:
            raise AppError(
                "INVALID_PROVIDER_RESULT", "An overall score requires dimension scores."
            )
        weights = job.rubric_snapshot["weights"]
        denominator = sum(weights[c] for c in available)
        if denominator <= 0:
            raise AppError(
                "INVALID_PROVIDER_RESULT",
                "Scored dimensions need positive rubric weights.",
            )
        expected = (
            sum(weights[c] * score for c, score in available.items()) / denominator
        )
        if abs(expected - result.scores.overall) > 0.05:
            raise AppError(
                "INVALID_PROVIDER_RESULT",
                "Overall score does not match the recorded rubric.",
            )
    if (
        recording.duration_seconds is None
        and result.execution_mode == "real"
        and result.participant_duration_seconds is not None
        and result.participant_duration_seconds > 0
    ):
        recording.duration_seconds = result.participant_duration_seconds
    if job.reference_id:
        reference = get(session, Reference, job.reference_id)
        reference_recording = get(session, Recording, reference.recording_id)
        if reference_recording.duration_seconds is not None and (
            result.reference_duration_seconds is None
            or abs(
                result.reference_duration_seconds - reference_recording.duration_seconds
            )
            > 0.01
        ):
            raise AppError(
                "INVALID_PROVIDER_RESULT",
                "Provider returned inconsistent reference duration.",
            )
        if (
            result.execution_mode == "real"
            and reference_recording.duration_seconds is None
            and result.reference_duration_seconds
        ):
            reference_recording.duration_seconds = result.reference_duration_seconds
    keys = []
    try:
        for name, series in result.feature_series.items():
            key = storage.save_json(series.model_dump(mode="json"))
            keys.append(key)
            session.add(
                FeatureSeries(
                    analysis_id=job.id,
                    feature_name=name,
                    unit=series.unit,
                    storage_key=key,
                    window_metadata=series.window_metadata,
                )
            )
        for flaw in result.flaws:
            session.add(
                DetectedFlaw(
                    analysis_id=job.id,
                    type=flaw.type,
                    start_seconds=flaw.start_seconds,
                    end_seconds=flaw.end_seconds,
                    severity=flaw.severity,
                    payload=flaw.model_dump(mode="json"),
                )
            )
        job.result_summary = result.model_dump(mode="json", exclude={"feature_series"})
        job.overall_score = result.scores.overall
        from app.models.entities import now

        job.status, job.progress_stage, job.progress_percent, job.completed_at = (
            "completed",
            "Completed",
            100,
            now(),
        )
        session.commit()
    except BaseException:
        session.rollback()
        for key in keys:
            storage.delete(key)
        raise


def result_for(session, storage, identifier):
    job = get(session, Analysis, identifier)
    if job.status != "completed" or not job.result_summary:
        raise AppError(
            "RESULT_NOT_READY", "This analysis has no completed result.", 409
        )
    value = dict(job.result_summary)
    value["feature_series"] = {
        row.feature_name: storage.read_json(row.storage_key)
        for row in session.scalars(
            select(FeatureSeries).where(FeatureSeries.analysis_id == job.id)
        )
    }
    return AnalysisResult.model_validate(value)


def delete_analysis(session, storage, identifier):
    job = get(session, Analysis, identifier)
    if job.status in ["queued", "processing"]:
        raise AppError("JOB_ACTIVE", "Cancel the job before deleting it.", 409)
    keys = [
        row.storage_key
        for row in session.scalars(
            select(FeatureSeries).where(FeatureSeries.analysis_id == job.id)
        )
    ]
    session.delete(job)
    session.commit()
    for key in keys:
        storage.delete(key)
