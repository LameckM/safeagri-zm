import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as c:
        yield c


GOOD = {"node_id": "node-02", "soil_moisture": 18, "temperature": 29, "humidity": 54}


def test_seeded_fields(client):
    fields = client.get("/fields").json()
    assert len(fields) == 4
    assert fields[1]["node_id"] == "node-02"


def test_good_reading_is_stored_without_timestamp(client):
    r = client.post("/readings", json=GOOD)
    assert r.status_code == 201
    assert r.json()["valid"] is True

    latest = client.get("/latest").json()
    assert len(latest) == 1
    assert latest[0]["field_id"] == 2
    assert latest[0]["soil_moisture"] == 18


def test_out_of_range_reading_is_flagged_not_trusted(client):
    client.post("/readings", json=GOOD)
    r = client.post("/readings", json={**GOOD, "soil_moisture": 999})
    assert r.status_code == 201
    assert r.json() == {"id": 2, "field_id": 2, "valid": False, "flag": "soil_moisture_out_of_range"}

    # not in normal reads, and /latest still shows the last good value
    assert len(client.get("/readings").json()) == 1
    assert client.get("/latest").json()[0]["soil_moisture"] == 18

    # but it is kept for the anomaly tests
    assert len(client.get("/readings", params={"include_invalid": True}).json()) == 2

    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "sensor_fault"


def test_unknown_node_is_rejected(client):
    r = client.post("/readings", json={**GOOD, "node_id": "node-99"})
    assert r.status_code == 404


def test_missing_field_is_rejected(client):
    bad = {k: v for k, v in GOOD.items() if k != "humidity"}
    assert client.post("/readings", json=bad).status_code == 422


def test_client_timestamp_is_kept(client):
    client.post("/readings", json={**GOOD, "timestamp": "2026-09-19T14:05:00Z"})
    row = client.get("/readings").json()[0]
    assert row["recorded_at"].startswith("2026-09-19T14:05:00")


def test_multiple_sensor_faults_are_reported_together(client):
    bad = {**GOOD, "temperature": 75, "humidity": 110}
    response = client.post("/readings", json=bad)
    assert response.status_code == 201
    assert response.json()["valid"] is False
    assert response.json()["flag"] == "temperature_out_of_range,humidity_out_of_range"

    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert "temperature" in alerts[0]["message"]
    assert "humidity" in alerts[0]["message"]


def test_repeated_sensor_faults_update_one_active_alert(client):
    bad = {**GOOD, "humidity": 110}
    client.post("/readings", json=bad)
    client.post("/readings", json={**bad, "humidity": 120})

    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert "120" in alerts[0]["message"]


def test_valid_reading_resolves_sensor_fault_alert(client):
    client.post("/readings", json={**GOOD, "humidity": 110})
    assert len(client.get("/alerts").json()) == 1

    client.post("/readings", json=GOOD)
    assert client.get("/alerts").json() == []
    resolved = client.get("/alerts", params={"resolved": True}).json()
    assert len(resolved) == 1
    assert resolved[0]["kind"] == "sensor_fault"
