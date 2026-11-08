"""Shared fixtures. Test clients come with a registered farmer and a key per node."""
import contextlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app


def _register_and_issue_keys(c):
    response = c.post("/auth/register", json={
        "full_name": "Test Farmer",
        "email": "farmer@example.com",
        "password": "test-password-123",
        "farm_name": "Test Farm",
        "location": "Luanshya",
        "setup_key": "test-initial-setup-key",
    })
    assert response.status_code == 201, response.text
    c.headers["Authorization"] = "Bearer " + response.json()["access_token"]

    c.node_keys = {}
    for field in c.get("/fields").json():
        issued = c.post(f"/fields/{field['id']}/node-key")
        assert issued.status_code == 200, issued.text
        c.node_keys[field["node_id"]] = issued.json()["node_key"]

    # Most tests are about readings, not credentials, so POST /readings sends
    # the right node's key unless the test supplies its own X-Node-Key header.
    original_post = c.post

    def post(url, *args, **kwargs):
        if url == "/readings":
            headers = dict(kwargs.get("headers") or {})
            node = (kwargs.get("json") or {}).get("node_id")
            if "X-Node-Key" not in headers and node in c.node_keys:
                headers["X-Node-Key"] = c.node_keys[node]
            kwargs["headers"] = headers
        return original_post(url, *args, **kwargs)

    c.post = post


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    @contextlib.contextmanager
    def factory(schedule_seconds=None):
        monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
        monkeypatch.setenv("SAFEAGRI_SECRET_KEY", "test-secret-key-for-safeagri-tests-only")
        monkeypatch.setenv("SAFEAGRI_INITIAL_SETUP_KEY", "test-initial-setup-key")
        if schedule_seconds is not None:
            monkeypatch.setenv("SAFEAGRI_SCHEDULE_SECONDS", schedule_seconds)
        with TestClient(app) as c:
            _register_and_issue_keys(c)
            yield c

    return factory


@pytest.fixture
def client(make_client):
    with make_client() as c:
        yield c


@pytest.fixture
def other_farm(client):
    """A second farm with its own owner. Signup can no longer create one, so insert it."""
    with db.get_conn() as conn:
        farm_id = conn.execute(
            "INSERT INTO farms (name, created_at) VALUES ('Other Farm', '2026-01-01T00:00:00.000+00:00')"
        ).lastrowid
        conn.execute(
            """INSERT INTO users (farm_id, full_name, email, password_hash, role, created_at)
               VALUES (?, 'Other Farmer', 'other@example.com', ?, 'farmer', '2026-01-01T00:00:00.000+00:00')""",
            (farm_id, auth.hash_password("other-password-123")),
        )
    login = client.post("/auth/login", json={"email": "other@example.com", "password": "other-password-123"})
    assert login.status_code == 200, login.text
    return SimpleNamespace(farm_id=farm_id, headers={"Authorization": "Bearer " + login.json()["access_token"]})
