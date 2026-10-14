"""Package the shareable tracked/non-ignored project without local data or weights."""

from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/submission/vocalis-submission.zip"


def main():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    names = sorted(set(n.decode("utf-8") for n in result.stdout.split(b"\0") if n))
    names = [name for name in names if not name.endswith(".zip")]
    forbidden = [
        ".venv/",
        "model-artifacts/",
        "backend/data/",
        "frontend/node_modules/",
        "frontend/dist/",
        "tmp/",
        ".git/",
    ]
    assert all(
        not name.startswith(tuple(forbidden)) and Path(name).name != ".env"
        for name in names
    )
    temporary = ROOT / "tmp/vocalis-submission-building.zip"
    temporary.parent.mkdir(exist_ok=True)
    assert OUTPUT.resolve().is_relative_to(ROOT) and temporary.resolve().is_relative_to(
        ROOT
    )
    with zipfile.ZipFile(
        temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for name in names:
            path = (ROOT / name).resolve()
            assert path.is_relative_to(ROOT)
            if path.is_file():
                archive.write(path, name)
    with zipfile.ZipFile(temporary) as archive:
        assert archive.testzip() is None
        for expected in [
            "clarity_analysis.py",
            "docs/benchmarks/clarity-verification.json",
            "docs/submission/technical-documentation.pdf",
            "scripts/verify_clarity_workflow.py",
            "docs/benchmarks/transcription-accuracy.json",
            "docs/benchmarks/automated-browser-verification.json",
            "dataset/asr_checks/manifest.json",
            "frontend/e2e/local-project.spec.ts",
            "docs/submission/vocalis-final-demo.mp4",
            "docs/submission/DEVPOST_DESCRIPTION.md",
            "docs/submission/SUBMIT_NOW.md",
            "docs/submission/deployment-verification.json",
            "docs/submission/public-browser-verification.json",
            "dataset/LICENSE_NOTES.md",
        ]:
            assert expected in archive.namelist()
        count = len(archive.namelist())
    temporary.replace(OUTPUT)
    print(
        f"Verified {count} files, {OUTPUT.stat().st_size/1024/1024:.2f} MB; model caches and private local data excluded."
    )


if __name__ == "__main__":
    main()
