from conftest import wav


def test_different_excerpts_from_same_source_cannot_leak_splits(client, inputs):
    common = dict(
        title="First source excerpt",
        source_id="original-speech-1",
        reference_recording_id=inputs["participant_recording_id"],
        transcript=inputs["transcript"],
        split="training",
    )
    assert client.post("/api/v1/datasets/groups", json=common).status_code == 201
    other = client.post(
        "/api/v1/recordings", files={"file": ("other.wav", wav(), "audio/wav")}
    ).json()
    response = client.post(
        "/api/v1/datasets/groups",
        json={**common, "reference_recording_id": other["id"], "split": "testing"},
    )
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "SPLIT_CONFLICT"
    )
