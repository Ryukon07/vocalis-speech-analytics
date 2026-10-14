"""Idempotently import the bundled real corpus into managed local storage."""

from pathlib import Path
import hashlib
import json
from fastapi import UploadFile
from starlette.datastructures import Headers
from sqlalchemy import select
from app.main import create_app
from app.models import (
    Recording,
    Reference,
    ContrastiveGroup,
    Variant,
    Annotation,
    Rubric,
)
from app.services.recording_service import upload

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "dataset/contrastive"


def run():
    manifest = json.loads((CORPUS / "manifest.json").read_text())
    app = create_app()
    with app.state.sessions() as db:
        if not db.scalar(select(Rubric).where(Rubric.name == "Contrastive delivery")):
            db.add(
                Rubric(
                    name="Contrastive delivery",
                    weights=dict(pacing=35, pitch=25, energy=25, pausing=15, clarity=0),
                    enabled_categories=["pacing", "pitch", "energy", "pausing"],
                )
            )
            db.commit()

        # Add a new rubric rather than mutating weights captured by historical analyses.
        if not db.scalar(
            select(Rubric).where(Rubric.name == "Complete delivery with clarity")
        ):
            db.add(
                Rubric(
                    name="Complete delivery with clarity",
                    weights=dict(
                        pacing=25, pitch=20, energy=20, pausing=15, clarity=20
                    ),
                    enabled_categories=[
                        "pacing",
                        "pitch",
                        "energy",
                        "pausing",
                        "clarity",
                    ],
                )
            )
            db.commit()

        def recording(metadata, filename, group, category):
            row = db.scalar(
                select(Recording).where(Recording.original_filename == filename)
            )
            if row:
                if (
                    hashlib.sha256(
                        app.state.storage.path(row.storage_key).read_bytes()
                    ).hexdigest()
                    != metadata["sha256"]
                ):
                    raise ValueError(
                        f"{filename}: imported audio changed. Preserve old analyses and import a new corpus version."
                    )
                return row
            path = (CORPUS / metadata["audio_file"]).resolve()
            if (
                not path.is_relative_to(CORPUS.resolve())
                or hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]
            ):
                raise ValueError("Invalid corpus path or checksum")
            with path.open("rb") as stream:
                row = upload(
                    db,
                    app.state.storage,
                    UploadFile(
                        filename=filename,
                        file=stream,
                        headers=Headers({"content-type": "audio/wav"}),
                    ),
                    app.state.settings.max_upload_mb,
                    category,
                )
            row.title = filename.removesuffix(".wav").replace("_", " ")
            row.transcript = group["transcript"]
            row.speaker_id = group["speaker_id"]
            row.source_url = group["source_url"]
            row.license = group["license"]
            row.notes = group["label_review"]
            db.commit()
            return row

        for group in manifest["groups"]:
            baseline = recording(
                group["reference"], group["id"] + "-reference.wav", group, "reference"
            )
            reference = db.scalar(
                select(Reference).where(Reference.recording_id == baseline.id)
            )
            if not reference:
                db.add(
                    Reference(
                        title=group["title"],
                        recording_id=baseline.id,
                        transcript=group["transcript"],
                        speaker_id=group["speaker_id"],
                        source_url=group["source_url"],
                        license=group["license"],
                    )
                )
                db.commit()
            row = db.scalar(
                select(ContrastiveGroup).where(
                    ContrastiveGroup.reference_recording_id == baseline.id
                )
            )
            if not row:
                row = ContrastiveGroup(
                    title=group["title"],
                    source_id=group["source_id"],
                    reference_recording_id=baseline.id,
                    transcript=group["transcript"],
                    speaker_id=group["speaker_id"],
                    split=group["split"],
                    provenance=json.dumps(
                        dict(
                            source_id=group["source_id"],
                            source_url=group["source_url"],
                            excerpt_start=group["source_start_seconds"],
                            excerpt_end=group["source_end_seconds"],
                            review=group["label_review"],
                        )
                    ),
                )
                db.add(row)
                db.commit()
            for variant in group["variants"]:
                audio = recording(variant, variant["id"] + ".wav", group, "variant")
                if not db.scalar(
                    select(Variant).where(
                        Variant.group_id == row.id, Variant.recording_id == audio.id
                    )
                ):
                    db.add(
                        Variant(
                            group_id=row.id,
                            recording_id=audio.id,
                            level=variant["level"],
                            flaw_labels=[
                                a["flaw_type"] for a in variant["annotations"]
                            ],
                            speaker_id=group["speaker_id"],
                            provenance=json.dumps(variant["transformation"]),
                        )
                    )
                    db.commit()
                for label in variant["annotations"]:
                    if not db.scalar(
                        select(Annotation).where(
                            Annotation.recording_id == audio.id,
                            Annotation.flaw_type == label["flaw_type"],
                        )
                    ):
                        db.add(
                            Annotation(
                                recording_id=audio.id,
                                **label,
                                source="controlled_edit",
                                notes="Exact edit bounds from the reproducible transformation; not a human quality judgment.",
                            )
                        )
                        db.commit()
            print(group["id"], "imported", flush=True)
    app.state.engine.dispose()


if __name__ == "__main__":
    run()
