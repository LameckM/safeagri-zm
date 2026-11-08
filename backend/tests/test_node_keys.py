"""Sensor-node credentials are required even though dashboard login is removed."""
from app import db

READING = {"node_id": "node-01", "soil_moisture": 40, "temperature": 28, "humidity": 55}


def send(client, key=None, node_id="node-01"):
    headers = {"X-Node-Key": key} if key is not None else {"X-Node-Key": ""}
    return client.post("/readings", json={**READING, "node_id": node_id}, headers=headers)


def test_correct_key_is_accepted(client):
    assert send(client, client.node_keys["node-01"]).status_code == 201


def test_missing_wrong_and_other_node_keys_are_rejected(client):
    assert send(client).status_code == 401
    assert send(client, "sak_not-the-key").status_code == 401
    assert send(client, client.node_keys["node-02"]).status_code == 401


def test_unknown_node_gets_same_answer_as_wrong_key(client):
    unknown = send(client, "sak_anything", node_id="node-99")
    wrong = send(client, "sak_anything", node_id="node-01")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_unprovisioned_node_cannot_report(client):
    with db.get_conn() as conn:
        conn.execute("UPDATE fields SET node_key_hash = NULL WHERE node_id = 'node-01'")
    assert send(client, client.node_keys["node-01"]).status_code == 401
    assert send(client).status_code == 401


def test_rotating_a_key_invalidates_the_old_key(client):
    old = client.node_keys["node-01"]
    new = client.post("/fields/1/node-key").json()["node_key"]
    assert new != old
    assert send(client, old).status_code == 401
    assert send(client, new).status_code == 201


def test_only_hashes_are_stored_and_returned_field_data_is_safe(client):
    key = client.node_keys["node-01"]
    with db.get_conn() as conn:
        stored = conn.execute("SELECT node_key_hash FROM fields WHERE node_id = 'node-01'").fetchone()[0]
    assert stored != key and key not in stored and len(stored) == 64
    for field in client.get("/fields").json():
        assert field["has_node_key"] is True
        assert "node_key_hash" not in field and "node_key" not in field


def test_node_key_issue_endpoint_returns_key_once(client):
    response = client.post("/fields/1/node-key")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"field_id", "node_id", "node_key"}


def test_alert_sync_does_not_require_farmer_login(client):
    assert client.post("/alerts/sync").status_code == 200
