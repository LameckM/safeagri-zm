"""Settings that depend on where or how the server is started."""
import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.main import app


def preflight(origin):
    return TestClient(app).options(
        "/auth/login",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )


def test_local_and_private_network_dashboards_are_allowed_on_any_port():
    for origin in (
        "http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:4173",
        "http://192.168.1.20:5173", "http://10.0.0.7:5173", "http://172.20.3.4:5173",
    ):
        assert preflight(origin).status_code == 200, origin


def test_other_websites_are_not_allowed():
    for origin in ("https://evil.example", "http://127.0.0.1.evil.example", "http://8.8.8.8:5173", "http://172.32.0.1:5173"):
        response = preflight(origin)
        assert "access-control-allow-origin" not in response.headers, origin


def test_default_database_does_not_depend_on_the_working_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    try:
        reloaded = importlib.reload(db)
        assert reloaded.DB_PATH.is_absolute()
        assert reloaded.DB_PATH == Path(db.__file__).resolve().parent.parent / "data" / "irrigation.db"
        assert tmp_path not in reloaded.DB_PATH.parents
    finally:
        monkeypatch.undo()
        importlib.reload(db)
