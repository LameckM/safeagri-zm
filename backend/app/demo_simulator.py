"""Automatic defence-demo sensor simulator.

The simulator runs inside the API process. Node connectivity is controlled
separately with: python -m backend.node_control node-01 offline|online
"""
import asyncio
import logging
import os
import random
import threading
from datetime import datetime, timezone

from .db import get_conn
from .validation import check_reading_flags, check_metric_flatline, check_trend_flags, describe_flag

log = logging.getLogger("safeagri.demo")
FAULTS = {}
FAULT_LOCK = threading.Lock()
FIELDS = {
    "node-01": {"moisture": 46.0, "temp": 27.0, "humidity": 58.0},
    "node-02": {"moisture": 34.0, "temp": 29.0, "humidity": 52.0},
    "node-03": {"moisture": 53.0, "temp": 26.0, "humidity": 61.0},
    "node-04": {"moisture": 22.0, "temp": 28.0, "humidity": 55.0},
}
FAULT_VALUES = {
    "humidity": {"low": -5.0, "high": 110.0},
    "temperature": {"low": -10.0, "high": 70.0},
    "soil_moisture": {"low": -5.0, "high": 110.0},
}


def set_demo_fault(node_id, metric, scenario):
    if node_id not in FIELDS:
        raise ValueError("Unknown demo node")
    with FAULT_LOCK:
        FAULTS[node_id] = {"metric": metric, "scenario": scenario, "held": None}
    return {"status": "fault_started", "node_id": node_id, "metric": metric, "scenario": scenario}


def clear_demo_fault(node_id):
    with FAULT_LOCK:
        FAULTS.pop(node_id, None)
    return {"status": "fault_cleared", "node_id": node_id}


def _reading(node_id, state, fault):
    state["moisture"] = max(3.0, min(95.0, state["moisture"] - random.uniform(0.12, 0.25)))
    state["temp"] = round(max(18, min(42, state["temp"] + random.uniform(-0.5, 0.5))), 1)
    state["humidity"] = round(max(25, min(90, state["humidity"] + random.uniform(-1.2, 1.2))), 1)
    result = {
        "node_id": node_id,
        "soil_moisture": round(state["moisture"], 1),
        "temperature": state["temp"],
        "humidity": state["humidity"],
    }
    if fault:
        metric, scenario = fault["metric"], fault["scenario"]
        if scenario in ("low", "high"):
            result[metric] = FAULT_VALUES[metric][scenario]
        elif scenario == "flatline":
            if fault["held"] is None:
                fault["held"] = result[metric]
            result[metric] = fault["held"]
    return result


def _store_reading(node_id, reading):
    received = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    flags = check_reading_flags(reading["soil_moisture"], reading["temperature"], reading["humidity"])
    with get_conn() as conn:
        field = conn.execute("SELECT id, name FROM fields WHERE node_id = ?", (node_id,)).fetchone()
        if field is None:
            return
        recent = conn.execute(
            "SELECT soil_moisture, temperature, humidity FROM readings WHERE field_id = ? ORDER BY id DESC LIMIT 10",
            (field["id"],),
        ).fetchall()
        last_ok = conn.execute(
            "SELECT soil_moisture, recorded_at FROM readings WHERE field_id = ? AND soil_moisture BETWEEN 0 AND 100 ORDER BY id DESC LIMIT 1",
            (field["id"],),
        ).fetchone()
        flags += check_metric_flatline("temperature", reading["temperature"], [r["temperature"] for r in recent])
        flags += check_metric_flatline("humidity", reading["humidity"], [r["humidity"] for r in recent])
        flags += check_trend_flags(reading["soil_moisture"], received, [r["soil_moisture"] for r in recent],
                                   (last_ok["soil_moisture"], last_ok["recorded_at"]) if last_ok else None)
        conn.execute(
            """INSERT INTO readings (field_id, soil_moisture, temperature, humidity, recorded_at, received_at, valid, flag)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (field["id"], reading["soil_moisture"], reading["temperature"], reading["humidity"],
             received, received, int(not flags), ",".join(flags) if flags else None),
        )
        if flags:
            message = f"{field['name']}: " + "; ".join(
                describe_flag(flag, reading["soil_moisture"], reading["temperature"], reading["humidity"]) for flag in flags
            )
            active = conn.execute("SELECT id FROM alerts WHERE field_id = ? AND kind = 'sensor_fault' AND resolved = 0",
                                  (field["id"],)).fetchone()
            if active:
                conn.execute("UPDATE alerts SET message = ? WHERE id = ?", (message, active["id"]))
            else:
                conn.execute("INSERT INTO alerts (field_id, kind, message, created_at) VALUES (?, 'sensor_fault', ?, ?)",
                             (field["id"], message, received))
        else:
            conn.execute("UPDATE alerts SET resolved = 1 WHERE field_id = ? AND kind = 'sensor_fault' AND resolved = 0",
                         (field["id"],))


async def demo_simulation_loop():
    interval = max(1.0, float(os.getenv("SAFEAGRI_DEMO_INTERVAL_SECONDS", "5")))
    log.info("Automatic demo sensor simulation started (interval=%ss)", interval)
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            with get_conn() as conn:
                for node_id in FIELDS:
                    conn.execute("INSERT OR IGNORE INTO node_status (node_id, online, updated_at) VALUES (?, 1, ?)",
                                 (node_id, now))
                statuses = {row["node_id"]: bool(row["online"]) for row in
                            conn.execute("SELECT node_id, online FROM node_status").fetchall()}
            for node_id, state in FIELDS.items():
                if not statuses.get(node_id, True):
                    continue
                with FAULT_LOCK:
                    fault = FAULTS.get(node_id)
                    reading = _reading(node_id, state, fault) if fault else _reading(node_id, state, None)
                _store_reading(node_id, reading)
            from .scheduler import sync_node_alerts
            sync_node_alerts()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Automatic demo simulation cycle failed")
        await asyncio.sleep(interval)
