import wave
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models import Recording, Transcription
from app.core.exceptions import AppError
from app.repositories.database import get

TYPES = {
    ".wav": {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"},
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".flac": {"audio/flac", "audio/x-flac"},
}


def upload(session, storage, file, max_mb, category):
    original = (file.filename or "").replace("\\", "/").split("/")[-1][:255]
    suffix = Path(original).suffix.lower()
    mime = (file.content_type or "").split(";")[0].lower()
    if suffix not in TYPES or mime not in TYPES[suffix]:
        raise AppError(
            "UNSUPPORTED_AUDIO",
            "Upload WAV, MP3 or FLAC with a matching audio media type.",
            415,
        )
    header = file.file.read(16)
    file.file.seek(0)
    valid = (
        (suffix == ".wav" and header[:4] == b"RIFF" and header[8:12] == b"WAVE")
        or (suffix == ".flac" and header[:4] == b"fLaC")
        or (
            suffix == ".mp3"
            and (
                header[:3] == b"ID3"
                or (len(header) > 1 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0)
            )
        )
    )
    if not valid:
        raise AppError(
            "INVALID_AUDIO", "The file header does not match its audio format.", 415
        )
    key, size = storage.save(file.file, suffix, max_mb * 1048576)
    duration = rate = channels = None
    try:
        if suffix == ".wav":
            try:
                with wave.open(str(storage.path(key))) as audio:
                    frames, rate, channels = (
                        audio.getnframes(),
                        audio.getframerate(),
                        audio.getnchannels(),
                    )
                    if frames == 0 or rate == 0:
                        raise ValueError("Empty audio")
                    expected_size = frames * audio.getsampwidth() * channels
                    if (
                        expected_size > size
                        or len(audio.readframes(frames)) != expected_size
                    ):
                        raise ValueError("Truncated audio")
                    duration = frames / rate
            except (wave.Error, EOFError, ValueError):
                raise AppError(
                    "INVALID_AUDIO",
                    "Invalid or unsupported WAV encoding. Use PCM WAV or a supported compressed format.",
                    415,
                )
        row = Recording(
            original_filename=original,
            storage_key=key,
            mime_type=mime,
            file_size=size,
            duration_seconds=duration,
            sample_rate=rate,
            channels=channels,
            title=Path(original).stem,
            category=category,
        )
        session.add(row)
        session.commit()
        return row
    except BaseException:
        session.rollback()
        storage.delete(key)
        raise


def delete_recording(session, storage, identifier):
    row = get(session, Recording, identifier)
    if session.scalar(
        select(Transcription.id).where(
            Transcription.recording_id == row.id,
            Transcription.status.in_(["queued", "processing"]),
        )
    ):
        raise AppError(
            "RECORD_IN_USE",
            "Cancel the active transcription before deleting this recording.",
            409,
        )
    key = row.storage_key
    try:
        session.delete(row)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise AppError(
            "RECORD_IN_USE",
            "Remove linked analyses, references and dataset groups before deleting this audio.",
            409,
        )
    storage.delete(key)
