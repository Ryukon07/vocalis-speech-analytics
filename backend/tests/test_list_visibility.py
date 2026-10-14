from app.repositories.database import visible_record_ids
from conftest import wav


def test_session_visibility_filters_before_pagination_and_resets(client):
    records = [
        client.post(
            "/api/v1/recordings",
            files={"file": (f"sample-{i}.wav", wav(), "audio/wav")},
        ).json()
        for i in range(5)
    ]
    allowed = frozenset(record["id"] for record in records[::2])
    token = visible_record_ids.set(allowed)
    try:
        first = client.get("/api/v1/recordings?limit=2").json()
        last = client.get("/api/v1/recordings?offset=2&limit=2").json()
        assert first["total"] == last["total"] == 3
        assert len(first["items"]) == 2 and len(last["items"]) == 1
        assert {item["id"] for item in first["items"] + last["items"]} == allowed
    finally:
        visible_record_ids.reset(token)
    assert client.get("/api/v1/recordings").json()["total"] == 5

    token = visible_record_ids.set(frozenset())
    try:
        empty = client.get("/api/v1/recordings").json()
        assert empty["total"] == 0 and empty["items"] == []
    finally:
        visible_record_ids.reset(token)
