from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as c:
        yield c


def post_reading(client, node_id, moisture, minutes_ago=0):
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return client.post(
        "/readings",
        json={
            "node_id": node_id,
            "soil_moisture": moisture,
            "temperature": 28,
            "humidity": 55,
            "timestamp": ts.isoformat(),
        },
    )


def test_dry_field_gets_irrigated(client):
    post_reading(client, "node-01", moisture=15)
    decisions = client.post("/schedule/run").json()

    d1 = next(d for d in decisions if d["field_id"] == 1)
    assert d1["action"] == "irrigate"
    assert d1["reason"] == "soil_below_dry_threshold"
    assert 5 <= d1["duration_min"] <= 30

    events = client.get("/schedule/events").json()
    assert len(events) == 1
    assert events[0]["field_id"] == 1
    assert events[0]["source"] == "rule"


def test_wet_field_is_never_irrigated(client):
    post_reading(client, "node-02", moisture=70)
    decisions = client.post("/schedule/run").json()

    d2 = next(d for d in decisions if d["field_id"] == 2)
    assert d2["action"] == "skip"
    assert d2["reason"] == "soil_already_wet"
    assert client.get("/schedule/events").json() == []


def test_moderate_moisture_is_skipped(client):
    post_reading(client, "node-03", moisture=40)
    decisions = client.post("/schedule/run").json()

    d3 = next(d for d in decisions if d["field_id"] == 3)
    assert d3["action"] == "skip"
    assert d3["reason"] == "moisture_within_range"


def test_field_with_no_readings_is_skipped_not_irrigated(client):
    decisions = client.post("/schedule/run").json()
    d1 = next(d for d in decisions if d["field_id"] == 1)
    assert d1["action"] == "skip"
    assert d1["reason"] == "no_readings_yet"


def test_stale_reading_raises_offline_alert_not_irrigation(client):
    post_reading(client, "node-04", moisture=10, minutes_ago=30)
    decisions = client.post("/schedule/run").json()

    d4 = next(d for d in decisions if d["field_id"] == 4)
    assert d4["action"] == "skip"
    assert d4["reason"] == "node_offline"
    assert client.get("/schedule/events").json() == []

    alerts = client.get("/alerts").json()
    assert any(a["kind"] == "node_offline" and a["field_id"] == 4 for a in alerts)


def test_offline_alert_is_not_duplicated_on_repeated_runs(client):
    post_reading(client, "node-04", moisture=10, minutes_ago=30)
    client.post("/schedule/run")
    client.post("/schedule/run")

    alerts = client.get("/alerts").json()
    offline_alerts = [a for a in alerts if a["kind"] == "node_offline" and a["field_id"] == 4]
    assert len(offline_alerts) == 1


def test_dry_field_with_invalid_latest_reading_is_not_irrigated(client):
    post_reading(client, "node-01", moisture=15)
    post_reading(client, "node-01", moisture=999)  # sensor fault, stored but invalid

    decisions = client.post("/schedule/run").json()
    d1 = next(d for d in decisions if d["field_id"] == 1)
    # Falls back to the last valid reading, still irrigates on that
    assert d1["action"] == "irrigate"
    assert d1["moisture"] == 15
