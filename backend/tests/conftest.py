"""Shared fixtures: isolated database and provisioned sensor keys."""
import contextlib
import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


def _provision_sensor_keys(client):
    client.node_keys = {}
    for field in client.get("/fields").json():
        response = client.post(f"/fields/{field['id']}/node-key")
        assert response.status_code == 200, response.text
        client.node_keys[field["node_id"]] = response.json()["node_key"]

    original_post = client.post
    def post(url, *args, **kwargs):
        if url == "/readings":
            headers = dict(kwargs.get("headers") or {})
            node = (kwargs.get("json") or {}).get("node_id")
            if "X-Node-Key" not in headers and node in client.node_keys:
                headers["X-Node-Key"] = client.node_keys[node]
            kwargs["headers"] = headers
        return original_post(url, *args, **kwargs)
    client.post = post


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    @contextlib.contextmanager
    def factory(schedule_seconds=None):
        monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
        if schedule_seconds is not None:
            monkeypatch.setenv("SAFEAGRI_SCHEDULE_SECONDS", schedule_seconds)
        else:
            monkeypatch.setenv("SAFEAGRI_SCHEDULE_SECONDS", "0")
        with TestClient(app) as client:
            _provision_sensor_keys(client)
            yield client
    return factory


@pytest.fixture
def client(make_client):
    with make_client() as client:
        yield client
