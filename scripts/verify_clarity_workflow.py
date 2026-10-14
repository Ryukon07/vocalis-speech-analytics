from pathlib import Path
import json
import time
import httpx

root = Path.cwd()
base = "http://127.0.0.1:8000/api/v1"
with httpx.Client(base_url=base, timeout=60) as c:
    files = c.get("/recordings?limit=100").raise_for_status().json()["items"]
    filename = "clarity-check-reagan_farewell_1989-opening-noise-10db.wav"
    participant = next((r for r in files if r["original_filename"] == filename), None)
    reference_record = next(
        r
        for r in files
        if r["original_filename"] == "reagan_farewell_1989-opening-reference.wav"
    )
    reference = next(
        r
        for r in c.get("/references?limit=100").raise_for_status().json()["items"]
        if r["recording_id"] == reference_record["id"]
    )
    if not participant:
        with (
            root / "dataset/clarity/reagan_farewell_1989-opening-noise-10db.wav"
        ).open("rb") as f:
            participant = (
                c.post(
                    "/recordings",
                    files={"file": (filename, f, "audio/wav")},
                    data={"category": "variant"},
                )
                .raise_for_status()
                .json()
            )
        c.patch(
            "/recordings/" + participant["id"],
            json={
                "title": "Clarity verification: known 10 dB noise",
                "transcript": reference["transcript"],
                "notes": "Deterministic noise verification; excluded from frozen delivery benchmark.",
            },
        ).raise_for_status()
    rubric = next(
        r
        for r in c.get("/rubrics?limit=100").raise_for_status().json()["items"]
        if r["name"] == "Complete delivery with clarity"
    )
    response = c.post(
        "/analyses",
        json=dict(
            participant_recording_id=participant["id"],
            reference_id=reference["id"],
            rubric_id=rubric["id"],
            transcript=reference["transcript"],
            settings={"enabled_categories": rubric["enabled_categories"]},
        ),
        headers={"Idempotency-Key": "clarity-noise-10db-v3.1.0"},
    ).raise_for_status()
    identifier = response.json()["id"]
    print("Clarity job:", identifier, flush=True)
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        job = c.get("/analyses/" + identifier).raise_for_status().json()
        if job["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.5)
    assert job["status"] == "completed", job
    result = c.get("/analyses/" + identifier + "/result").raise_for_status().json()
    assert (
        result["clarity"]["available"]
        and result["scores"]["dimensions"]["clarity"] < 100
    )
    assert any(f["type"] == "recognition_difficulty" for f in result["flaws"])
    for fmt in ["json", "csv", "pdf"]:
        c.get("/analyses/" + identifier + "/export/" + fmt).raise_for_status()
    (root / "docs/benchmarks/clarity-website-result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        "Verified clarity:",
        result["scores"]["dimensions"]["clarity"],
        "flaws",
        len(result["flaws"]),
        flush=True,
    )
