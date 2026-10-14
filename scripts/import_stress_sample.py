"""Import and evaluate the supplementary combined stress case through the live API."""

from pathlib import Path
import json
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / "dataset/stress_samples"


def main():
    data = json.loads((folder / "manifest.json").read_text())
    with httpx.Client(base_url="http://127.0.0.1:8000/api/v1", timeout=60) as client:
        records = client.get("/recordings?limit=100").raise_for_status().json()["items"]
        recording = next(
            (
                r
                for r in records
                if r["original_filename"] == "combined-severe-training-stress.wav"
            ),
            None,
        )
        if not recording:
            with (folder / "combined-severe.wav").open("rb") as f:
                recording = (
                    client.post(
                        "/recordings",
                        files={
                            "file": (
                                "combined-severe-training-stress.wav",
                                f,
                                "audio/wav",
                            )
                        },
                        data={"category": "variant"},
                    )
                    .raise_for_status()
                    .json()
                )
            client.patch(
                "/recordings/" + recording["id"],
                json={
                    "title": "Combined severe delivery stress case",
                    "transcript": data["transcript"],
                    "speaker_id": "Ronald Reagan",
                    "notes": data["benchmark_role"],
                },
            ).raise_for_status()
        baseline = next(
            r
            for r in records
            if r["original_filename"] == "reagan_challenger_1986-opening-reference.wav"
        )
        reference = next(
            r
            for r in client.get("/references?limit=100")
            .raise_for_status()
            .json()["items"]
            if r["recording_id"] == baseline["id"]
        )
        rubric = next(
            r
            for r in client.get("/rubrics?limit=100").raise_for_status().json()["items"]
            if r["name"] == "Contrastive delivery"
        )
        group = next(
            g
            for g in client.get("/datasets/groups?limit=100")
            .raise_for_status()
            .json()["items"]
            if g["reference_recording_id"] == baseline["id"]
        )
        if not any(v["recording_id"] == recording["id"] for v in group["variants"]):
            client.post(
                "/datasets/groups/" + group["id"] + "/variants",
                json={
                    "recording_id": recording["id"],
                    "level": 5,
                    "flaw_labels": list({a["flaw_type"] for a in data["annotations"]}),
                    "speaker_id": "Ronald Reagan",
                    "provenance": json.dumps(data["transformations"]),
                },
            ).raise_for_status()
        existing = (
            client.get(
                "/datasets/annotations?recording_id=" + recording["id"] + "&limit=100"
            )
            .raise_for_status()
            .json()["items"]
        )
        for label in data["annotations"]:
            if not any(
                a["flaw_type"] == label["flaw_type"]
                and abs(a["start_seconds"] - label["start_seconds"]) < 0.001
                for a in existing
            ):
                client.post(
                    "/datasets/annotations",
                    json={
                        "recording_id": recording["id"],
                        **label,
                        "source": "controlled_edit",
                        "notes": data["benchmark_role"],
                    },
                ).raise_for_status()
        job = (
            client.post(
                "/analyses",
                json={
                    "participant_recording_id": recording["id"],
                    "reference_id": reference["id"],
                    "rubric_id": rubric["id"],
                    "transcript": data["transcript"],
                },
                headers={"Idempotency-Key": "combined-training-stress-v1"},
            )
            .raise_for_status()
            .json()
        )
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and job["status"] not in [
            "completed",
            "failed",
            "cancelled",
        ]:
            time.sleep(0.5)
            job = client.get("/analyses/" + job["id"]).raise_for_status().json()
        assert job["status"] == "completed", job
        result = (
            client.get("/analyses/" + job["id"] + "/result").raise_for_status().json()
        )
        (folder / "website-result.json").write_text(json.dumps(result, indent=2))
        (folder / "website-job.json").write_text(json.dumps(job, indent=2))
        print(
            "Combined severe report:",
            job["id"],
            "score",
            result["scores"]["overall"],
            "flaws",
            len(result["flaws"]),
        )


if __name__ == "__main__":
    main()
