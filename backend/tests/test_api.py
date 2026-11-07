from fastapi.testclient import TestClient

from app import db
from app.main import app

GOOD = {"node_id": "node-02", "soil_moisture": 18, "temperature": 29, "humidity": 54}


def test_seeded_fields(client):
    fields = client.get("/fields").json()
    assert len(fields) == 4
    assert fields[1]["node_id"] == "node-02"
    assert all(field["farm_id"] == 1 for field in fields)


def test_good_reading_is_stored_without_timestamp(client):
    r = client.post("/readings", json=GOOD)
    assert r.status_code == 201
    assert r.json()["valid"] is True
    latest = client.get("/latest").json()
    assert len(latest) == 4
    node_two = next(row for row in latest if row["field_id"] == 2)
    assert node_two["soil_moisture"] == 18


def test_out_of_range_reading_is_flagged_not_trusted(client):
    client.post("/readings", json=GOOD)
    r = client.post("/readings", json={**GOOD, "soil_moisture": 999})
    assert r.status_code == 201
    assert r.json() == {"id": 2, "field_id": 2, "valid": False, "flag": "soil_moisture_out_of_range"}
    assert len(client.get("/readings").json()) == 1
    node_two = next(row for row in client.get("/latest").json() if row["field_id"] == 2)
    assert node_two["soil_moisture"] == 18
    assert len(client.get("/readings", params={"include_invalid": True}).json()) == 2
    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "sensor_fault"


def test_unknown_node_is_rejected(client):
    r = client.post("/readings", json={**GOOD, "node_id": "node-99"}, headers={"X-Node-Key": "sak_anything"})
    assert r.status_code == 401


def test_missing_field_is_rejected(client):
    bad = {k: v for k, v in GOOD.items() if k != "humidity"}
    assert client.post("/readings", json=bad).status_code == 422


def test_client_timestamp_is_kept(client):
    client.post("/readings", json={**GOOD, "timestamp": "2026-09-19T14:05:00Z"})
    row = client.get("/readings").json()[0]
    assert row["recorded_at"].startswith("2026-09-19T14:05:00")


def test_all_out_of_range_sensor_metrics_are_flagged_and_one_alert_updated(client):
    bad = {**GOOD, "temperature": 75, "humidity": 110}
    first = client.post("/readings", json=bad)
    assert first.status_code == 201
    assert first.json()["valid"] is False
    assert first.json()["flag"] == "temperature_out_of_range,humidity_out_of_range"
    assert len(client.get("/alerts").json()) == 1
    client.post("/readings", json={**bad, "temperature": 80})
    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert "80" in alerts[0]["message"]


def test_valid_reading_resolves_sensor_fault_alert(client):
    client.post("/readings", json={**GOOD, "humidity": 110})
    assert len(client.get("/alerts").json()) == 1
    client.post("/readings", json=GOOD)
    assert client.get("/alerts").json() == []
    assert len(client.get("/alerts", params={"resolved": True}).json()) == 1


def test_latest_returns_all_fields_and_latest_packet_health(client):
    client.post("/readings", json=GOOD)
    client.post("/readings", json={**GOOD, "humidity": 110})
    rows = client.get("/latest").json()
    assert len(rows) == 4
    node_two = next(row for row in rows if row["field_id"] == 2)
    assert node_two["soil_moisture"] == 18
    assert node_two["last_packet_valid"] == 0


def test_protected_endpoints_reject_missing_token(client):
    client.headers.pop("Authorization")
    for path in ("/auth/me", "/fields", "/readings", "/latest", "/alerts", "/schedule/events"):
        assert client.get(path).status_code == 401


def test_public_registration_is_disabled(client):
    response = client.post("/auth/register", json={
        "full_name": "Another User", "email": "another@example.com",
        "password": "another-password-123", "farm_name": "Another Farm",
    })
    assert response.status_code == 403
    assert "registration is disabled" in response.json()["detail"].lower()


def test_field_creation_is_disabled(client):
    response = client.post("/fields", json={"name": "North Plot", "node_id": "node-new"})
    assert response.status_code == 405


def test_owner_can_rename_demo_field(client):
    field_id = client.get("/fields").json()[0]["id"]
    updated = client.patch(f"/fields/{field_id}", json={"name": "Renamed Field"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed Field"


def test_login_and_current_user(client):
    client.headers.pop("Authorization")
    response = client.post("/auth/login", json={"email": "owner@example.com", "password": "test-owner-password-123"})
    assert response.status_code == 200
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    assert client.get("/auth/me").json()["email"] == "owner@example.com"


def test_owner_account_is_seeded_from_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "owner.db")
    monkeypatch.setenv("SAFEAGRI_SECRET_KEY", "test-secret-key-for-safeagri-tests-only")
    monkeypatch.setenv("SAFEAGRI_OWNER_EMAIL", "configured@example.com")
    monkeypatch.setenv("SAFEAGRI_OWNER_PASSWORD", "configured-owner-password")
    monkeypatch.setenv("SAFEAGRI_DEMO_SIMULATION", "0")
    with TestClient(app) as c:
        response = c.post("/auth/login", json={"email": "configured@example.com", "password": "configured-owner-password"})
        assert response.status_code == 200
        assert response.json()["user"]["role"] == "owner"
        assert c.post("/auth/register", json={}).status_code == 403


# --- trend rules: flatline and implausible drop -----------------------------

from datetime import datetime, timedelta, timezone  # noqa: E402

_BASE = datetime(2026, 9, 19, 14, 0, tzinfo=timezone.utc)


def _send(client, moisture, minutes):
    body = {**GOOD, "soil_moisture": moisture, "temperature": 29.0 + minutes / 100, "humidity": 54.0 + minutes / 100, "timestamp": (_BASE + timedelta(minutes=minutes)).isoformat()}
    return client.post("/readings", json=body).json()


def test_flatline_is_flagged_on_fourth_identical_reading_and_clears_when_value_moves(client):
    results = [_send(client, 40.0, m * 5) for m in range(5)]
    assert [r["valid"] for r in results] == [True, True, True, False, False]
    assert results[3]["flag"] == "soil_moisture_flatline"
    alerts = client.get("/alerts").json()
    assert len(alerts) == 1 and "stuck" in alerts[0]["message"]
    assert _send(client, 39.8, 25)["valid"] is True
    assert client.get("/alerts").json() == []


def test_fast_drop_is_flagged_but_normal_drying_and_rain_are_not(client):
    assert _send(client, 40.0, 0)["valid"] is True
    assert _send(client, 39.8, 5)["valid"] is True      # normal drying
    assert _send(client, 60.0, 10)["valid"] is True     # rain or irrigation
    bad = _send(client, 50.0, 15)                        # 10 points in five minutes
    assert bad["valid"] is False
    assert bad["flag"] == "soil_moisture_implausible_drop"
    assert "faster than soil can dry" in client.get("/alerts").json()[0]["message"]


def test_large_fall_after_a_long_gap_is_not_a_fault(client):
    assert _send(client, 40.0, 0)["valid"] is True
    assert _send(client, 30.0, 180)["valid"] is True     # three hours later



def test_humidity_flatline_is_detected_and_clears_when_humidity_changes(client):
    results = []
    for minute in range(4):
        results.append(client.post("/readings", json={
            **GOOD,
            "soil_moisture": 40.0 + minute * 0.1,
            "temperature": 27.0 + minute * 0.5,
            "humidity": 54.0,
            "timestamp": (_BASE + timedelta(minutes=minute * 5)).isoformat(),
        }).json())
    assert [result["valid"] for result in results] == [True, True, True, False]
    assert results[-1]["flag"] == "humidity_flatline"
    assert "humidity stuck" in client.get("/alerts").json()[0]["message"]

    recovered = client.post("/readings", json={
        **GOOD,
        "soil_moisture": 40.5,
        "temperature": 29.5,
        "humidity": 53.5,
        "timestamp": (_BASE + timedelta(minutes=20)).isoformat(),
    })
    assert recovered.json()["valid"] is True
    assert client.get("/alerts").json() == []


def test_temperature_flatline_is_detected(client):
    results = []
    for minute in range(4):
        results.append(client.post("/readings", json={
            **GOOD,
            "soil_moisture": 40.0 + minute * 0.1,
            "temperature": 28.0,
            "humidity": 50.0 + minute,
            "timestamp": (_BASE + timedelta(minutes=minute * 5)).isoformat(),
        }).json())
    assert [result["valid"] for result in results] == [True, True, True, False]
    assert results[-1]["flag"] == "temperature_flatline"



def test_demo_sensor_fault_controls_are_owner_protected(client):
    from app.demo_simulator import FAULTS
    FAULTS.clear()
    client.headers.pop("Authorization")
    assert client.post("/demo/fault", json={"field_id": 1, "metric": "humidity", "scenario": "high"}).status_code == 401
    client.headers["Authorization"] = "Bearer " + client.post("/auth/login", json={
        "email": "owner@example.com", "password": "test-owner-password-123"
    }).json()["access_token"]
    fields = client.get("/fields").json()
    field_id = fields[0]["id"]
    started = client.post("/demo/fault", json={"field_id": field_id, "metric": "humidity", "scenario": "high"})
    assert started.status_code == 200
    assert started.json()["status"] == "fault_started"
    assert FAULTS["node-01"]["metric"] == "humidity"
    cleared = client.post("/demo/fault/clear", json={"field_id": field_id})
    assert cleared.status_code == 200
    assert cleared.json()["status"] == "fault_cleared"
    assert "node-01" not in FAULTS


def test_demo_fault_routes_reject_invalid_metric(client):
    field_id = client.get("/fields").json()[0]["id"]
    response = client.post("/demo/fault", json={"field_id": field_id, "metric": "battery", "scenario": "high"})
    assert response.status_code == 422
