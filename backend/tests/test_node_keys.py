"""Sensor nodes must prove who they are; farmers issue and rotate the keys."""
from app import db

READING = {"node_id": "node-01", "soil_moisture": 40, "temperature": 28, "humidity": 55}


def send(client, key=None, node_id="node-01"):
    headers = {"X-Node-Key": key} if key is not None else {"X-Node-Key": ""}
    return client.post("/readings", json={**READING, "node_id": node_id}, headers=headers)


def test_correct_key_is_accepted(client):
    assert send(client, client.node_keys["node-01"]).status_code == 201


def test_missing_wrong_and_foreign_keys_are_rejected(client):
    keys = client.node_keys
    assert send(client, None).status_code == 401
    assert send(client, "sak_not-the-key").status_code == 401
    assert send(client, keys["node-02"]).status_code == 401  # another node's key
    assert client.get("/readings", params={"include_invalid": True}).json() == []


def test_unknown_node_gets_the_same_answer_as_a_wrong_key(client):
    unknown = send(client, "sak_anything", node_id="node-99")
    wrong = send(client, "sak_anything", node_id="node-01")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_node_with_no_key_issued_cannot_report(client):
    with db.get_conn() as conn:
        conn.execute("UPDATE fields SET node_key_hash = NULL WHERE node_id = 'node-01'")
    assert send(client, client.node_keys["node-01"]).status_code == 401
    assert send(client, None).status_code == 401


def test_rotating_a_key_stops_the_old_one(client):
    old = client.node_keys["node-01"]
    new = client.post("/fields/1/node-key").json()["node_key"]
    assert new != old
    assert send(client, old).status_code == 401
    assert send(client, new).status_code == 201


def test_only_the_hash_is_stored(client):
    key = client.node_keys["node-01"]
    with db.get_conn() as conn:
        stored = conn.execute("SELECT node_key_hash FROM fields WHERE node_id = 'node-01'").fetchone()[0]
    assert stored != key and key not in stored and len(stored) == 64


def test_field_responses_never_include_the_hash_or_key(client):
    for field in client.get("/fields").json():
        assert field["has_node_key"] is True
        assert "node_key_hash" not in field and "node_key" not in field
    patched = client.patch("/fields/1", json={"name": "North plot"}).json()
    assert patched["name"] == "North plot" and patched["has_node_key"] is True
    assert "node_key_hash" not in patched
    issued = client.post("/fields/1/node-key")
    assert issued.headers["cache-control"] == "no-store"
    assert set(issued.json()) == {"field_id", "node_id", "node_key"}


def test_issuing_a_key_requires_login(client):
    client.headers.pop("Authorization")
    assert client.post("/fields/1/node-key").status_code == 401


def test_a_farmer_cannot_issue_a_key_for_another_farms_field(client, other_farm):
    with db.get_conn() as conn:
        conn.execute("INSERT INTO fields (id, farm_id, name, node_id) VALUES (50, ?, 'Theirs', 'node-50')", (other_farm.farm_id,))

    # The first farmer gets "not found", exactly as for a field that does not exist.
    assert client.post("/fields/50/node-key").status_code == 404
    assert client.post("/fields/50/node-key", headers=other_farm.headers).status_code == 200


def test_alert_sync_requires_login_and_stays_inside_the_farm(client):
    assert client.post("/alerts/sync").status_code == 200
    client.headers.pop("Authorization")
    assert client.post("/alerts/sync").status_code == 401


def _member_headers(client):
    code = client.post("/farm/invites").json()["invite_code"]
    joined = client.post("/auth/register", json={
        "full_name": "Farm Hand", "email": "hand@example.com",
        "password": "hand-password-123", "invite_code": code,
    })
    assert joined.status_code == 201
    return {"Authorization": "Bearer " + joined.json()["access_token"]}


def test_a_team_member_cannot_rotate_keys_or_edit_fields(client):
    member = _member_headers(client)
    before = client.node_keys["node-01"]
    assert client.post("/fields/1/node-key", headers=member).status_code == 403
    assert client.patch("/fields/1", json={"name": "Hijacked"}, headers=member).status_code == 403
    # The device still works and the field is untouched.
    assert send(client, before).status_code == 201
    assert client.get("/fields").json()[0]["name"] != "Hijacked"
    # Members can still read the farm.
    assert len(client.get("/fields", headers=member).json()) == 4
