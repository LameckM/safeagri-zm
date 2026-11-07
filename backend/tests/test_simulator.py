"""Regression tests for targeted sensor faults and node isolation."""
import importlib.util
import sys
from pathlib import Path

import pytest

SIMULATOR_PATH = Path(__file__).resolve().parents[2] / "simulator" / "simulate.py"
spec = importlib.util.spec_from_file_location("safeagri_simulator", SIMULATOR_PATH)
simulator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = simulator
spec.loader.exec_module(simulator)


class FakeResponse:
    text = ""

    def __init__(self, status_code):
        self.status_code = status_code

    @staticmethod
    def json():
        return {"valid": True}


class FakeClient:
    instances = []

    def __init__(self):
        self.posts = []
        self.headers_sent = []
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append((url, json))
        self.headers_sent.append(headers)
        return FakeResponse(201)


KEYS = {node: f"key-for-{node}" for node in ("node-01", "node-02", "node-03", "node-04")}


@pytest.fixture(autouse=True)
def reset_client():
    FakeClient.instances.clear()


def test_sensor_scenario_changes_only_selected_metric():
    reading = {
        "node_id": "node-01",
        "soil_moisture": 42.0,
        "temperature": 28.0,
        "humidity": 55.0,
    }
    result = simulator.apply_scenario(reading.copy(), "humidity", "high", {})
    assert result["humidity"] == 108.0
    assert result["soil_moisture"] == 42.0
    assert result["temperature"] == 28.0


def test_flatline_holds_only_selected_metric():
    held = {}
    first = {"node_id": "node-01", "humidity": 61.0, "temperature": 27.0, "soil_moisture": 40.0}
    second = {"node_id": "node-01", "humidity": 58.0, "temperature": 29.0, "soil_moisture": 39.0}
    assert simulator.apply_scenario(first, "humidity", "flatline", held)["humidity"] == 61.0
    result = simulator.apply_scenario(second, "humidity", "flatline", held)
    assert result["humidity"] == 61.0
    assert result["temperature"] == 29.0
    assert result["soil_moisture"] == 39.0


def test_offline_scenario_sends_no_sensor_packet():
    reading = {"node_id": "node-01", "soil_moisture": 40.0, "temperature": 28.0, "humidity": 55.0}
    assert simulator.apply_scenario(reading, "humidity", "offline", {}) is None


def test_targeting_one_node_keeps_other_nodes_reporting(monkeypatch):
    monkeypatch.setattr(simulator.httpx, "Client", FakeClient)
    monkeypatch.setattr(simulator.time, "sleep", lambda _seconds: None)

    simulator.run(fast=True, hours=0.00001, scenario="offline", node="node-01", node_keys=KEYS)

    client = FakeClient.instances[0]
    reading_posts = [
        payload for url, payload in client.posts
        if url.endswith("/readings")
    ]
    reported_nodes = [payload["node_id"] for payload in reading_posts]
    assert reported_nodes.count("node-01") == 1  # initial packet only
    assert set(reported_nodes) == {"node-01", "node-02", "node-03", "node-04"}


def test_targeted_humidity_fault_does_not_change_other_nodes(monkeypatch):
    monkeypatch.setattr(simulator.httpx, "Client", FakeClient)
    monkeypatch.setattr(simulator.time, "sleep", lambda _seconds: None)

    simulator.run(
        fast=True,
        hours=0.00001,
        sensor="humidity",
        scenario="high",
        node="node-01",
        node_keys=KEYS,
    )

    reading_posts = [
        payload for url, payload in FakeClient.instances[0].posts
        if url.endswith("/readings")
    ]
    by_node = {payload["node_id"]: payload for payload in reading_posts}
    assert by_node["node-01"]["humidity"] == 108.0
    assert by_node["node-01"]["temperature"] <= 60.0
    assert by_node["node-01"]["soil_moisture"] <= 100.0
    assert all(by_node[node]["humidity"] <= 100.0 for node in ("node-02", "node-03", "node-04"))


def test_each_reading_carries_its_own_nodes_key(monkeypatch):
    monkeypatch.setattr(simulator.httpx, "Client", FakeClient)
    monkeypatch.setattr(simulator.time, "sleep", lambda _seconds: None)

    simulator.run(fast=True, hours=0.00001, node_keys=KEYS)

    client = FakeClient.instances[0]
    assert len(client.posts) == 4
    for (url, payload), headers in zip(client.posts, client.headers_sent):
        assert url.endswith("/readings")
        assert headers == {"X-Node-Key": KEYS[payload["node_id"]]}


def test_simulator_does_not_run_without_node_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(simulator.httpx, "Client", FakeClient)
    monkeypatch.setattr(simulator, "KEYS_PATH", tmp_path / "missing.json")

    simulator.run(fast=True, hours=0.00001)

    assert FakeClient.instances == []
