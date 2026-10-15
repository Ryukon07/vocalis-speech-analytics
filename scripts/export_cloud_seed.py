"""Build a cloud seed from protected public records, excluding every guest item."""
from pathlib import Path
import json
import shutil
import sys
import tarfile
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.repositories.database import database
from app.models import Base, Recording, Rubric, Reference, ContrastiveGroup, Variant, Annotation, Analysis, DetectedFlaw, FeatureSeries


def main():
    source = ROOT / "tmp/public-demo"
    target = ROOT / "tmp/azure-cloud-seed"
    target.mkdir(parents=True, exist_ok=True)
    seed = target / "seed"
    seed.mkdir(exist_ok=True)
    destination = seed / "state.sqlite"
    assert not destination.exists(), "Refusing to replace an existing seed database."
    protected = set(json.loads((source / "seed-manifest.json").read_text())["protected_ids"])
    src_engine, src_sessions = database("sqlite:///" + (source / "state.sqlite").as_posix())
    dst_engine, dst_sessions = database("sqlite:///" + destination.as_posix())
    Base.metadata.create_all(dst_engine)
    copied, files, totals = set(), set(), {}
    (seed / "storage").mkdir(exist_ok=True)
    models = [Recording, Rubric, Reference, ContrastiveGroup, Variant, Annotation, Analysis, DetectedFlaw, FeatureSeries]
    with src_sessions() as src, dst_sessions() as dst:
        for model in models:
            rows = list(src.scalars(select(model).where(model.id.in_(protected))))
            totals[model.__tablename__] = len(rows)
            for row in rows:
                if model is Recording:
                    assert row.original_filename != "speech-1791959497867.wav"
                dst.add(model(**{column.name: getattr(row, column.name) for column in model.__table__.columns}))
                copied.add(row.id)
                if model in (Recording, FeatureSeries): files.add(row.storage_key)
            dst.commit()
    assert totals["recordings"] == 91 and totals["analyses"] == 10
    for key in files:
        original = (source / "storage" / key).resolve()
        assert original.is_relative_to((source / "storage").resolve())
        shutil.copy2(original, seed / "storage" / key)
    src_engine.dispose(); dst_engine.dispose()
    (seed / "seed-manifest.json").write_text(json.dumps(dict(protected_ids=sorted(copied), public_seed_only=True, totals=totals), indent=2) + "\n")
    archive = target / "vocalis-public-seed.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for path in sorted(seed.rglob("*")):
            if path.is_file() and not path.name.endswith(("-wal", "-shm")):
                bundle.add(path, arcname=path.relative_to(seed).as_posix())
    print(f"Prepared public-only cloud seed: {totals['recordings']} recordings, {totals['analyses']} real reports, {archive.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__": main()
