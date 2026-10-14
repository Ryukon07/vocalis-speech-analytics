from sqlalchemy import select
from app.models import Recording, ContrastiveGroup, Variant, Annotation
from app.repositories.database import get
from app.core.exceptions import AppError
from app.schemas.contracts import GroupOut, VariantOut


def group_out(session, row):
    value = GroupOut.model_validate(row)
    value.variants = [
        VariantOut.model_validate(v)
        for v in session.scalars(select(Variant).where(Variant.group_id == row.id))
    ]
    return value


def validate_group(session, data, current_id=None):
    get(session, Recording, data.reference_recording_id)
    if data.source_id:
        for existing in session.scalars(
            select(ContrastiveGroup).where(ContrastiveGroup.source_id == data.source_id)
        ):
            if existing.id != current_id and existing.split != data.split:
                raise AppError(
                    "SPLIT_CONFLICT",
                    "All excerpts and variants of a source speech must stay in the same split.",
                    409,
                )
    # A source recording and all variants belong to a single split; do not permit hidden leakage.
    linked = select(Variant.group_id).where(
        Variant.recording_id == str(data.reference_recording_id)
    )
    for existing in session.scalars(
        select(ContrastiveGroup).where(
            (
                ContrastiveGroup.reference_recording_id
                == str(data.reference_recording_id)
            )
            | ContrastiveGroup.id.in_(linked)
        )
    ).all():
        if existing.id != current_id and existing.split != data.split:
            raise AppError(
                "SPLIT_CONFLICT",
                "This source recording already belongs to another dataset split.",
                409,
            )
    if current_id and session.scalar(
        select(Variant.id).where(
            Variant.group_id == current_id,
            Variant.recording_id == str(data.reference_recording_id),
        )
    ):
        raise AppError(
            "INVALID_SOURCE", "A paired variant cannot also be the group source."
        )


def validate_annotation(session, data):
    recording = get(session, Recording, data.recording_id)
    if recording.duration_seconds is None:
        raise AppError(
            "DURATION_UNKNOWN",
            "Timestamp annotations require a known duration. Use a PCM WAV recording.",
        )
    if data.end_seconds > recording.duration_seconds:
        raise AppError(
            "INTERVAL_OUT_OF_BOUNDS", "Annotation exceeds recording duration."
        )


def add_variant(session, group_id, data):
    group = get(session, ContrastiveGroup, group_id)
    recording = get(session, Recording, data.recording_id)
    if recording.id == group.reference_recording_id:
        raise AppError(
            "INVALID_VARIANT", "The source recording cannot be its own variant."
        )
    linked = select(Variant.group_id).where(Variant.recording_id == recording.id)
    for other in session.scalars(
        select(ContrastiveGroup).where(
            (ContrastiveGroup.reference_recording_id == recording.id)
            | ContrastiveGroup.id.in_(linked)
        )
    ).all():
        if other.split != group.split:
            raise AppError(
                "SPLIT_CONFLICT", "This variant already belongs to another split.", 409
            )
    if (
        recording.transcript
        and recording.transcript.split() != group.transcript.split()
    ):
        raise AppError(
            "TRANSCRIPT_MISMATCH", "Variant transcript must match the group transcript."
        )
    row = Variant(group_id=group.id, **data.model_dump(mode="json"))
    session.add(row)
    session.commit()
    return row
