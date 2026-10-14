"""Export only allowlisted public seed records and real reports for static hosting."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import shutil
import sqlite3
import httpx

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "tmp/public-demo"
SITE = ROOT / "tmp/permanent-demo/site"


def main():
    protected = set(json.loads((STATE / "seed-manifest.json").read_text())["protected_ids"])
    output = SITE / "archive"
    output.mkdir(parents=True, exist_ok=True)
    snapshot = {}
    with httpx.Client(base_url="http://127.0.0.1:8001/api/v1", timeout=90) as client:
        def get(path):
            return client.get(path).raise_for_status().json()

        for path in ["/recordings", "/references", "/rubrics", "/analyses", "/datasets/groups", "/datasets/annotations"]:
            items = get(path + "?limit=100")["items"]
            snapshot[path] = [item for item in items if item["id"] in protected]
            for item in snapshot[path]:
                if path == "/datasets/groups":
                    item["variants"] = [variant for variant in item["variants"] if variant["id"] in protected]
                snapshot[path + "/" + item["id"]] = item
        assert len(snapshot["/analyses"]) == 10
        for job in snapshot["/analyses"]:
            assert job["execution_mode"] == "real" and job["status"] == "completed"
            identifier = job["id"]
            snapshot[f"/analyses/{identifier}/result"] = get(f"/analyses/{identifier}/result")
            folder = output / "exports"
            folder.mkdir(exist_ok=True)
            for extension in ["json", "csv", "pdf"]:
                data = client.get(f"/analyses/{identifier}/export/{extension}").raise_for_status().content
                if extension == "pdf":
                    assert data.startswith(b"%PDF-")
                (folder / f"{identifier}.{extension}").write_bytes(data)
        provider = get("/providers")
        provider.update(ready=False, message="Saved real inference reports. This free hosted viewer does not run new model jobs.")
        snapshot["/providers"] = provider
        caps = get("/providers/capabilities")
        caps["automatic_transcription"] = False
        snapshot["/providers/capabilities"] = caps
    jobs = snapshot["/analyses"]
    scores = [job["overall_score"] for job in jobs if job["overall_score"] is not None]
    counts = Counter(flaw["type"] for job in jobs for flaw in snapshot[f"/analyses/{job['id']}/result"]["flaws"])
    snapshot["/dashboard"] = dict(total=len(jobs), completed=len(jobs), real_completed=len(jobs), average_score=sum(scores)/len(scores), references=len(snapshot["/references"]), groups=len(snapshot["/datasets/groups"]), recent=jobs[:5], frequent_flaws=[dict(type=name, count=count) for name,count in counts.most_common(6)])
    audio = output / "audio"
    audio.mkdir(exist_ok=True)
    hashes = {}
    with sqlite3.connect(STATE / "state.sqlite") as database:
        for record in snapshot["/recordings"]:
            assert record["original_filename"] != "speech-1791959497867.wav"
            key, = database.execute("select storage_key from recordings where id=?", (record["id"],)).fetchone()
            source = (STATE / "storage" / key).resolve()
            assert source.is_relative_to((STATE / "storage").resolve())
            destination = audio / f"{record['id']}.wav"
            assert source.read_bytes()[:4] == b"RIFF"
            shutil.copy2(source, destination)
            hashes[record["id"]] = hashlib.sha256(destination.read_bytes()).hexdigest()
    serialized = json.dumps(snapshot, ensure_ascii=False)
    assert "speech-1791959497867.wav" not in serialized
    (output / "snapshot.json").write_text(serialized, encoding="utf-8")
    (output / "provenance.json").write_text(json.dumps(dict(source="Allowlisted public seed database, real completed model jobs", report_ids=[job["id"] for job in jobs], recordings=len(hashes), audio_sha256=hashes, new_inference=False, laptop_required=False), indent=2) + "\n")
    downloads = SITE / "downloads"
    downloads.mkdir(exist_ok=True)
    for filename in ["vocalis-final-demo.mp4", "technical-documentation.pdf"]:
        shutil.copy2(ROOT / "docs/submission" / filename, downloads / filename)
    (SITE / ".nojekyll").write_text("")
    print(f"Exported {len(jobs)} real reports, {len(hashes)} allowlisted public recordings and all report downloads.")


if __name__ == "__main__":
    main()
