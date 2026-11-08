from app import db

GOOD = {"node_id": "node-02", "soil_moisture": 18, "temperature": 29, "humidity": 54}


def test_seeded_fields_are_public_and_have_no_account_dependency(client):
    fields = client.get("/fields").json()
    assert len(fields) == 4
    assert fields[1]["node_id"] == "node-02"
    assert "farm_id" not in fields[1]


def test_good_reading_is_stored_without_timestamp(client):
    response = client.post("/readings", json=GOOD)
    assert response.status_code == 201 and response.json()["valid"] is True
    latest = client.get("/latest").json()
    assert len(latest) == 4
    assert next(row for row in latest if row["field_id"] == 2)["soil_moisture"] == 18


def test_out_of_range_reading_is_flagged_not_trusted(client):
    client.post("/readings", json=GOOD)
    response = client.post("/readings", json={**GOOD, "soil_moisture": 999})
    assert response.status_code == 201 and response.json()["valid"] is False
    assert response.json()["flag"] == "soil_moisture_out_of_range"
    assert len(client.get("/readings").json()) == 1
    assert len(client.get("/readings", params={"include_invalid": True}).json()) == 2
    assert client.get("/alerts").json()[0]["kind"] == "sensor_fault"


def test_unknown_node_is_rejected(client):
    response = client.post("/readings", json={**GOOD, "node_id": "node-99"}, headers={"X-Node-Key": "sak_anything"})
    assert response.status_code == 401


def test_missing_field_is_rejected(client):
    bad = {key: value for key, value in GOOD.items() if key != "humidity"}
    assert client.post("/readings", json=bad).status_code == 422


def test_client_timestamp_is_kept(client):
    client.post("/readings", json={**GOOD, "timestamp": "2026-09-19T14:05:00Z"})
    assert client.get("/readings").json()[0]["recorded_at"].startswith("2026-09-19T14:05:00")


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


def test_dashboard_data_endpoints_are_open_without_login(client):
    assert client.get("/fields").status_code == 200
    assert client.get("/latest").status_code == 200
    assert client.get("/readings").status_code == 200
    assert client.get("/alerts").status_code == 200
    assert client.get("/schedule/events").status_code == 200


def test_field_rename_works_without_account_login(client):
    updated = client.patch("/fields/1", json={"name": "North Plot"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "North Plot"
    assert "node_key_hash" not in updated.json()


def test_field_creation_remains_disabled(client):
    assert client.post("/fields", json={"name": "North Plot", "node_id": "node-new"}).status_code == 405
