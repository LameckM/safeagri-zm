"""Signup after the first account is invite-only, and an invite joins the owner's farm."""
from app import db

NEW_USER = {
    "full_name": "Farm Hand", "email": "hand@example.com", "password": "hand-password-123",
}


def invite(client):
    response = client.post("/farm/invites")
    assert response.status_code == 201, response.text
    return response.json()["invite_code"]


def signup(client, code, **overrides):
    return client.post("/auth/register", json={**NEW_USER, "invite_code": code, **overrides})


def test_signup_without_an_invite_is_refused_after_the_first_account(client):
    response = signup(client, None)
    assert response.status_code == 403
    assert "invite code is required" in response.json()["detail"]
    assert signup(client, "inv_made-up-code").status_code == 403


def test_a_farm_cannot_be_created_by_signup_after_the_first_account(client):
    # Naming a farm and sending the setup key still does not open a new farm.
    response = client.post("/auth/register", json={
        **NEW_USER, "farm_name": "Rival Farm", "setup_key": "test-initial-setup-key",
    })
    assert response.status_code == 403


def test_an_invited_person_joins_the_owners_farm(client):
    owner_farm = client.get("/auth/me").json()["farm_id"]
    response = signup(client, invite(client))
    assert response.status_code == 201, response.text
    user = response.json()["user"]
    assert user["farm_id"] == owner_farm
    assert user["role"] == "member"
    assert user["farm_name"] == "Test Farm"

    member = {"Authorization": "Bearer " + response.json()["access_token"]}
    assert len(client.get("/fields", headers=member).json()) == 4
    assert client.get("/auth/me", headers=member).json()["farm_id"] == owner_farm


def test_an_invite_works_once(client):
    code = invite(client)
    assert signup(client, code).status_code == 201
    again = signup(client, code, email="second@example.com")
    assert again.status_code == 403
    assert again.json()["detail"] == "Invalid or expired invite code"


def test_expired_revoked_and_unknown_codes_get_the_same_answer(client):
    expired = invite(client)
    revoked_response = client.post("/farm/invites").json()
    with db.get_conn() as conn:
        conn.execute("UPDATE invites SET expires_at = '2000-01-01T00:00:00.000+00:00' WHERE id = 1")
    assert client.delete(f"/farm/invites/{revoked_response['id']}").status_code == 204

    answers = {
        signup(client, expired).json()["detail"],
        signup(client, revoked_response["invite_code"]).json()["detail"],
        signup(client, "inv_never-issued").json()["detail"],
    }
    assert answers == {"Invalid or expired invite code"}


def test_a_taken_email_does_not_use_up_the_invite(client):
    code = invite(client)
    taken = signup(client, code, email="farmer@example.com")
    assert taken.status_code == 409
    assert signup(client, code).status_code == 201


def test_codes_are_stored_hashed_and_never_listed(client):
    code = invite(client)
    with db.get_conn() as conn:
        stored = conn.execute("SELECT code_hash FROM invites").fetchone()[0]
    assert code not in stored and len(stored) == 64
    listing = client.get("/farm/invites").json()
    assert code not in str(listing) and stored not in str(listing)


def test_listing_shows_pending_used_and_expired(client):
    used_code = invite(client)
    signup(client, used_code)
    invite(client)
    invite(client)
    with db.get_conn() as conn:
        conn.execute("UPDATE invites SET expires_at = '2000-01-01T00:00:00.000+00:00' WHERE id = 3")
    rows = {row["id"]: row for row in client.get("/farm/invites").json()}
    assert rows[1]["status"] == "used" and rows[1]["used_by_name"] == "Farm Hand"
    assert rows[2]["status"] == "pending" and rows[2]["used_by_name"] is None
    assert rows[3]["status"] == "expired"


def test_a_used_invite_cannot_be_revoked(client):
    code = invite(client)
    signup(client, code)
    assert client.delete("/farm/invites/1").status_code == 409


def test_members_cannot_manage_invites(client):
    member = {"Authorization": "Bearer " + signup(client, invite(client)).json()["access_token"]}
    assert client.post("/farm/invites", headers=member).status_code == 403
    assert client.get("/farm/invites", headers=member).status_code == 403
    assert client.delete("/farm/invites/1", headers=member).status_code == 403


def test_invites_require_login(client):
    client.headers.pop("Authorization")
    assert client.post("/farm/invites").status_code == 401
    assert client.get("/farm/invites").status_code == 401


def test_an_owner_cannot_see_or_revoke_another_farms_invites(client, other_farm):
    mine = client.post("/farm/invites").json()
    theirs = client.post("/farm/invites", headers=other_farm.headers).json()
    assert [row["id"] for row in client.get("/farm/invites").json()] == [mine["id"]]
    assert client.delete(f"/farm/invites/{theirs['id']}").status_code == 404
    # And an invite from the other farm joins the other farm, not this one.
    joined = signup(client, theirs["invite_code"]).json()["user"]
    assert joined["farm_id"] == other_farm.farm_id


def test_pending_invites_are_capped(client):
    for _ in range(20):
        assert client.post("/farm/invites").status_code == 201
    assert client.post("/farm/invites").status_code == 409


def test_the_first_account_still_needs_a_farm_name(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "first.db")
    monkeypatch.setenv("SAFEAGRI_SECRET_KEY", "test-secret-key-for-safeagri-tests-only")
    monkeypatch.setenv("SAFEAGRI_INITIAL_SETUP_KEY", "test-initial-setup-key")
    with TestClient(app) as c:
        body = {**NEW_USER, "setup_key": "test-initial-setup-key"}
        assert c.post("/auth/register", json=body).status_code == 422
        assert c.post("/auth/register", json={**body, "farm_name": "First Farm"}).status_code == 201
