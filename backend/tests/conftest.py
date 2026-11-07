"""Shared fixtures. Test clients come with a registered farmer and a key per node."""
import contextlib

import pytest
from fastapi.testclient import TestClient

from app import db
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
