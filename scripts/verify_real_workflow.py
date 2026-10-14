"""Exercise real local HTTP jobs, evidence persistence, playback and all exports."""

from pathlib import Path
import json
import time
import sys
import re
import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000/api/v1"


def main():
    # Verify the actual frontend server, including SPA fallback and built assets.
    with httpx.Client(base_url="http://127.0.0.1:5173", timeout=10) as frontend:
        page = frontend.get("/").raise_for_status()
        assert "vocalis" in page.text.lower()
        assert frontend.get("/analyze").status_code == 200
        asset = re.search(r'src="([^"]+\.js)"', page.text)
        assert asset, "The built frontend entry script is missing"
        script = frontend.get(asset.group(1)).raise_for_status()
        assert "javascript" in script.headers["content-type"]
        assert frontend.get("/assets/missing-verification.js").status_code == 404
        assert frontend.get("/%2e%2e%2fpackage.json").status_code == 403
    with httpx.Client(base_url=BASE, timeout=60) as client:
        provider = client.get("/providers").raise_for_status().json()
        assert provider["ready"] and provider["execution_mode"] == "real", provider
        records = client.get("/recordings?limit=100").raise_for_status().json()["items"]
        references = (
            client.get("/references?limit=100").raise_for_status().json()["items"]
        )
        rubric = next(
            r
            for r in client.get("/rubrics?limit=100").raise_for_status().json()["items"]
            if r["name"] == "Complete delivery with clarity"
        )
        group_id = "reagan_challenger_1986-opening"
        baseline = next(
            r for r in records if r["original_filename"] == group_id + "-reference.wav"
        )
        reference = next(r for r in references if r["recording_id"] == baseline["id"])
        identifiers = []
        for variant in [
            "near-perfect",
            "rushed-mild",
            "rushed-severe",
            "slow",
            "pause",
            "low-energy",
            "monotone",
        ]:
            participant = next(
                r
                for r in records
                if r["original_filename"] == group_id + "-" + variant + ".wav"
            )
            payload = dict(
                participant_recording_id=participant["id"],
                reference_id=reference["id"],
                rubric_id=rubric["id"],
                transcript=reference["transcript"],
                settings={"enabled_categories": rubric["enabled_categories"]},
            )
            response = client.post(
                "/analyses",
                json=payload,
                headers={
                    "Idempotency-Key": "local-verification-"
                    + provider["provider_version"]
                    + "-"
                    + variant
                },
            ).raise_for_status()
            identifiers.append((variant, response.json()["id"]))
        deadline = time.monotonic() + 600
        for variant, identifier in identifiers:
            while time.monotonic() < deadline:
                job = client.get("/analyses/" + identifier).raise_for_status().json()
                if job["status"] in ["completed", "failed", "cancelled"]:
                    break
                time.sleep(0.5)
            assert job["status"] == "completed", job
            result = (
                client.get("/analyses/" + identifier + "/result")
                .raise_for_status()
                .json()
            )
            assert result["execution_mode"] == "real"
            assert result["alignment"]["words"]
            assert result["clarity"] and result["clarity"]["available"]
            assert (
                result["scores"]["dimensions"]["clarity"] == result["clarity"]["score"]
            )
            assert all(
                s["time_axis"] == "participant_aligned"
                for s in result["feature_series"].values()
            )
            for fmt in ["json", "csv", "pdf"]:
                export = client.get(
                    "/analyses/" + identifier + "/export/" + fmt
                ).raise_for_status()
                assert export.content
                if fmt == "pdf":
                    assert export.content.startswith(b"%PDF-")
            audio = client.get(
                "/recordings/" + job["participant_recording_id"] + "/audio",
                headers={"Range": "bytes=0-99"},
            ).raise_for_status()
            assert audio.status_code == 206 and len(audio.content) == 100
            print(
                variant,
                identifier,
                "score",
                result["scores"]["overall"],
                "flaws",
                len(result["flaws"]),
                flush=True,
            )
        # A genuine transcription job produces a draft without overwriting verified source text.
        response = client.post(
            "/recordings/" + baseline["id"] + "/transcriptions"
        ).raise_for_status()
        identifier = response.json()["id"]
        while time.monotonic() < deadline:
            job = client.get("/transcriptions/" + identifier).raise_for_status().json()
            if job["status"] in ["completed", "failed", "cancelled"]:
                break
            time.sleep(0.5)
        assert job["status"] == "completed" and len(job["transcript"].split()) > 20, job
        print(
            "Real local transcription completed:",
            len(job["transcript"].split()),
            "words",
            flush=True,
        )
        report = dict(
            provider=provider,
            jobs=[dict(variant=v, id=i) for v, i in identifiers],
            transcription_id=identifier,
        )
        (ROOT / "docs/benchmarks/website-verification.json").write_text(
            json.dumps(report, indent=2)
        )


if __name__ == "__main__":
    main()
