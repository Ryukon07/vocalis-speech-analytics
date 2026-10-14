"""Compare real local API transcription jobs with four downloaded gold transcripts."""
import hashlib
import json
from pathlib import Path
import sys
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clarity_analysis import normalized_tokens, word_errors

BASE = "http://127.0.0.1:8000/api/v1"

def main():
    manifest = json.loads((ROOT / "dataset/asr_checks/manifest.json").read_text())
    # Acceptance is specified before recognition; raw comparisons remain in the report.
    report = dict(source=manifest, protocol="Four fixed clips, three real API jobs per clip; no gold text supplied to ASR",
        acceptance=dict(aggregate_wer_max=0.10, individual_wer_max=0.15, repeats_identical=True), samples=[])
    with httpx.Client(base_url=BASE, timeout=60) as client:
        report["provider"] = client.get("/providers").raise_for_status().json()
        for sample in manifest["samples"]:
            path = ROOT / "dataset/asr_checks" / sample["file"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == sample["sha256"]
            with path.open("rb") as file:
                recording = client.post("/recordings", files={"file": (path.name, file, "audio/wav")}, data={"category": "participant"}).raise_for_status().json()
            item = dict(sample_id=sample["id"], recording_id=recording["id"], expected=sample["text"], runs=[])
            # Keep the public recordings for reproducible browser checks and later manual review.
            for repeat in range(3):
                start = time.monotonic()
                job = client.post(f"/recordings/{recording['id']}/transcriptions").raise_for_status().json()
                deadline = start + 600
                while job["status"] in ("queued", "processing") and time.monotonic() < deadline:
                    time.sleep(0.4)
                    job = client.get("/transcriptions/" + job["id"]).raise_for_status().json()
                assert job["status"] == "completed", job
                errors = word_errors(normalized_tokens(sample["text"]), normalized_tokens(job["transcript"]))
                item["runs"].append(dict(repeat=repeat+1, job_id=job["id"], model=job["model_name"], recognized=job["transcript"], elapsed_seconds=round(time.monotonic()-start, 3), **errors))
                print(sample["id"], repeat+1, job["model_name"], errors["word_error_rate"], job["transcript"], flush=True)
            item["repeats_identical"] = len({r["recognized"] for r in item["runs"]}) == 1
            report["samples"].append(item)
    first = [s["runs"][0] for s in report["samples"]]
    report["aggregate_wer"] = sum(r["substitutions"] + r["deletions"] + r["insertions"] for r in first) / sum(len(normalized_tokens(s["expected"])) for s in report["samples"])
    report["passed"] = report["aggregate_wer"] <= 0.10 and all(r["word_error_rate"] <= 0.15 for r in first) and all(s["repeats_identical"] for s in report["samples"])
    output = ROOT / "docs/benchmarks/transcription-accuracy.json"
    output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print("Aggregate WER:", report["aggregate_wer"], "Passed:", report["passed"], flush=True)
    assert report["passed"], "Accuracy acceptance failed; inspect the saved report before changing model configuration."

if __name__ == "__main__": main()
