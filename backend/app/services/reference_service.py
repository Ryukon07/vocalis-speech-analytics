from sqlalchemy import select
from app.models import Analysis, Reference, Recording
from app.repositories.database import get
from app.core.exceptions import AppError


def update_reference(session, identifier, data):
    row = get(session, Reference, identifier)
    get(session, Recording, data.recording_id)
    in_use = session.scalar(
        select(Analysis.id).where(Analysis.reference_id == row.id).limit(1)
    )
    if in_use and (
        row.recording_id != str(data.recording_id)
        or row.transcript != data.transcript
        or row.profile != data.profile
    ):
        raise AppError(
            "REFERENCE_IN_USE",
            "This reference is used by saved analyses. Create a new reference to change its audio, transcript or processed profile.",
            409,
        )
    for name, value in data.model_dump(mode="json").items():
        setattr(row, name, value)
    session.commit()
    return row
