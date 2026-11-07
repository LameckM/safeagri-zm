"""Shared fixtures: one configured owner and four demo node credentials."""
import contextlib
import pytest
from fastapi.testclient import TestClient
from app import db
from app.main import app

OWNER_EMAIL = "owner@safeagri.local"
OWNER_PASSWORD = "test-owner-password-123"

@pytest.fixture
def make_client(tmp_path, monkeypatch):
    @contextlib.contextmanager
    def factory(schedule_seconds=None):
        monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
        monkeypatch.setenv("SAFEAGRI_SECRET_KEY", "test-secret-key-for-safeagri-tests-only")
        monkeypatch.setenv("SAFEAGRI_OWNER_EMAIL", OWNER_EMAIL)
        monkeypatch.setenv("SAFEAGRI_OWNER_PASSWORD", OWNER_PASSWORD)
        monkeypatch.setenv("SAFEAGRI_OWNER_NAME", "Test Owner")
        monkeypatch.setenv("SAFEAGRI_FARM_NAME", "Test Farm")
        monkeypatch.setenv("SAFEAGRI_DEMO_SIMULATION", "0")
        if schedule_seconds is not None:
            monkeypatch.setenv("SAFEAGRI_SCHEDULE_SECONDS", schedule_seconds)
        with TestClient(app) as c:
            login = c.post("/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
            assert login.status_code == 200, login.text
            c.headers["Authorization"] = "Bearer " + login.json()["access_token"]
            c.node_keys = {}
            for field in c.get("/fields").json():
                issued = c.post(f"/fields/{field['id']}/node-key")
                assert issued.status_code == 200, issued.text
                c.node_keys[field["node_id"]] = issued.json()["node_key"]
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
            yield c
    return factory

@pytest.fixture
def client(make_client):
    with make_client() as c:
        yield c
