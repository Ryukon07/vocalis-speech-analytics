"""Explicit opt-in demo seed. Synthetic tones are test audio, not spoken speech."""

import io
import math
import struct
import wave
from fastapi import UploadFile
from starlette.datastructures import Headers
from sqlalchemy import select
from app.main import create_app
from app.models import (
    Recording,
    Reference,
    Rubric,
    ContrastiveGroup,
    Variant,
    Annotation,
)
from app.schemas.contracts import (
    DEFAULT_WEIGHTS,
    AnalysisCreate,
    RubricOut,
    AnalysisSettings,
)
from app.services.recording_service import upload
from app.services.analysis_service import create_analysis, persist_result
from app.ml.registry import get_provider
from app.ml.schemas import ProviderRequest

TRANSCRIPT = "Every voice carries an idea. When we speak with purpose, we give that idea room to grow. Pause, listen, and let each word carry its meaning."


def tone(frequency):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        frames = bytearray()
        for i in range(16000 * 18):
            amplitude = 0.12 * (0.3 + 0.7 * math.sin(i / 16000 * 2) ** 2)
            frames.extend(
                struct.pack(
                    "<h",
                    int(
                        32767
                        * amplitude
                        * math.sin(2 * math.pi * frequency * i / 16000)
                    ),
                )
            )
        audio.writeframes(frames)
    stream.seek(0)
    return stream


def seed():
    app = create_app()
    with app.state.sessions() as session:
        rubric = session.scalar(select(Rubric).limit(1))
        if not rubric:
            rubric = Rubric(
                name="Balanced delivery",
                weights=DEFAULT_WEIGHTS,
                enabled_categories=list(DEFAULT_WEIGHTS),
            )
            session.add(rubric)
            session.commit()
        if not app.state.settings.enable_demo_mode:
            print(
                "Default rubric ready. Demo mode is disabled; sample fixtures were not created."
            )
            return
        if session.scalar(
            select(Recording).where(
                Recording.original_filename == "demo-reference-tone.wav"
            )
        ):
            print("Demo already exists; no duplicate sample data added.")
            return
        provider = get_provider(app.state.settings)
        if provider.get_capabilities().execution_mode != "mock":
            print("Default rubric ready. Run demo seeding only with the mock provider.")
            return
        reference_audio = upload(
            session,
            app.state.storage,
            UploadFile(
                file=tone(190),
                filename="demo-reference-tone.wav",
                headers=Headers({"content-type": "audio/wav"}),
            ),
            50,
            "demo",
        )
        participant = upload(
            session,
            app.state.storage,
            UploadFile(
                file=tone(220),
                filename="demo-participant-tone.wav",
                headers=Headers({"content-type": "audio/wav"}),
            ),
            50,
            "demo",
        )
        for recording in [reference_audio, participant]:
            recording.transcript, recording.license, recording.notes = (
                TRANSCRIPT,
                "CC0 - generated test fixture",
                "Synthetic tone fixture. Not a speech recording.",
            )
        reference = Reference(
            title="DEMO · Purposeful delivery (tone fixture)",
            recording_id=reference_audio.id,
            transcript=TRANSCRIPT,
            license=reference_audio.license,
        )
        group = ContrastiveGroup(
            title="DEMO · Contrastive tone fixtures",
            reference_recording_id=reference_audio.id,
            transcript=TRANSCRIPT,
            split="training",
            provenance="Generated deterministic tones; UI demonstration only.",
        )
        session.add_all([reference, group])
        session.commit()
        session.add(
            Variant(
                group_id=group.id,
                recording_id=participant.id,
                level=3,
                flaw_labels=["pacing"],
                provenance="Illustrative fixture",
            )
        )
        session.add(
            Annotation(
                recording_id=participant.id,
                flaw_type="excessive_pace",
                start_seconds=4.68,
                end_seconds=7.56,
                severity=3,
                source="mock_fixture",
                notes="Illustrative label; not a measured speech flaw.",
            )
        )
        session.commit()
        data = AnalysisCreate(
            participant_recording_id=participant.id,
            reference_id=reference.id,
            rubric_id=rubric.id,
            transcript=TRANSCRIPT,
        )
        job, _ = create_analysis(session, data, provider, "seed-demo-v1")
        request = ProviderRequest(
            job_id=job.id,
            participant_path=app.state.storage.path(participant.storage_key),
            participant_duration_seconds=18,
            reference_path=app.state.storage.path(reference_audio.storage_key),
            reference_duration_seconds=18,
            transcript=TRANSCRIPT,
            reference_transcript=TRANSCRIPT,
            rubric=RubricOut.model_validate(rubric),
            settings=AnalysisSettings(),
        )
        persist_result(session, app.state.storage, job, provider.analyze(request))
        print(
            "Demo fixtures and completed mock report created. No real speech analysis was performed."
        )


if __name__ == "__main__":
    seed()
