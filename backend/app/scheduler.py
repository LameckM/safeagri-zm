"""Farm-scoped rule-based irrigation scheduler and alert synchronization."""
import os
from datetime import datetime, timedelta, timezone
from .db import get_conn

DRY_THRESHOLD, WET_THRESHOLD, TARGET_MOISTURE = 25.0, 60.0, 45.0
STALE_MINUTES = float(os.getenv("SAFEAGRI_STALE_MINUTES", "15"))
MIN_DURATION_MIN, MAX_DURATION_MIN = 5, 30

def _latest_packet(conn, field_id):
    return conn.execute("SELECT * FROM readings WHERE field_id = ? ORDER BY received_at DESC, id DESC LIMIT 1", (field_id,)).fetchone()

def _is_stale(received_at, now):
    stamp = datetime.fromisoformat(received_at)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return now - stamp > timedelta(minutes=STALE_MINUTES)

def _forced_offline(conn, node_id):
    row = conn.execute("SELECT online FROM node_status WHERE node_id = ?", (node_id,)).fetchone()
    return row is not None and not bool(row["online"])

def evaluate_field(conn, field_row):
    if _forced_offline(conn, field_row["node_id"]):
        return {"field_id": field_row["id"], "field_name": field_row["name"], "action": "skip", "reason": "node_offline", "duration_min": None, "moisture": None}
    latest = _latest_packet(conn, field_row["id"])
    decision = {"field_id": field_row["id"], "field_name": field_row["name"], "action": "skip", "reason": None, "duration_min": None, "moisture": None}
    if latest is None:
        decision["reason"] = "no_readings_yet"
        return decision
    if _is_stale(latest["received_at"], datetime.now(timezone.utc)):
        decision["reason"] = "node_offline"
        return decision
    if not latest["valid"]:
        decision["reason"] = "sensor_fault"
        return decision
    moisture = latest["soil_moisture"]
    decision["moisture"] = moisture
    if moisture >= WET_THRESHOLD:
        decision["reason"] = "soil_already_wet"
    elif moisture <= DRY_THRESHOLD:
        decision["action"] = "irrigate"
        decision["reason"] = "soil_below_dry_threshold"
        decision["duration_min"] = max(MIN_DURATION_MIN, min(MAX_DURATION_MIN, round(TARGET_MOISTURE - moisture)))
    else:
        decision["reason"] = "moisture_within_range"
    return decision

def _sync_alert(conn, field_id, kind, active, message, now_text):
    row = conn.execute("SELECT id FROM alerts WHERE field_id = ? AND kind = ? AND resolved = 0", (field_id, kind)).fetchone()
    if active and row:
        conn.execute("UPDATE alerts SET message = ? WHERE id = ?", (message, row["id"]))
    elif active:
        conn.execute("INSERT INTO alerts (field_id, kind, message, created_at) VALUES (?, ?, ?, ?)", (field_id, kind, message, now_text))
    elif row:
        conn.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (row["id"],))

def sync_node_alerts(farm_id=None):
    now = datetime.now(timezone.utc)
    now_text = now.isoformat(timespec="milliseconds")
    with get_conn() as conn:
        sql, params = "SELECT * FROM fields", []
        if farm_id is not None:
            sql += " WHERE farm_id = ?"
            params.append(farm_id)
        for field in conn.execute(sql + " ORDER BY id", params).fetchall():
            latest = _latest_packet(conn, field["id"])
            forced_offline = _forced_offline(conn, field["node_id"])
            if latest is None and not forced_offline:
                continue
            stale = forced_offline or (latest is not None and _is_stale(latest["received_at"], now))
            _sync_alert(conn, field["id"], "node_offline", stale, f"{field['name']}: no sensor packet received in over {STALE_MINUTES:g} minutes", now_text)
            dry = not stale and latest is not None and bool(latest["valid"]) and latest["soil_moisture"] <= DRY_THRESHOLD
            dry_message = f"{field['name']}: soil moisture is low ({latest['soil_moisture']}%). Irrigation is recommended." if latest is not None else f"{field['name']}: soil moisture is low. Irrigation is recommended."
            _sync_alert(conn, field["id"], "dry_soil", dry, dry_message, now_text)

def run_schedule(farm_id=None):
    sync_node_alerts(farm_id)
    now_text = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    decisions = []
    with get_conn() as conn:
        sql, params = "SELECT * FROM fields", []
        if farm_id is not None:
            sql += " WHERE farm_id = ?"
            params.append(farm_id)
        for field in conn.execute(sql + " ORDER BY id", params).fetchall():
            decision = evaluate_field(conn, field)
            decisions.append(decision)
            last = conn.execute("SELECT action FROM irrigation_events WHERE field_id = ? ORDER BY id DESC LIMIT 1", (field["id"],)).fetchone()
            if decision["action"] == "irrigate" and (last is None or last["action"] != "open"):
                conn.execute("""INSERT INTO irrigation_events (field_id, action, source, duration_min, created_at) VALUES (?, 'open', 'rule', ?, ?)""", (field["id"], decision["duration_min"], now_text))
            elif decision["action"] != "irrigate" and last is not None and last["action"] == "open":
                conn.execute("""INSERT INTO irrigation_events (field_id, action, source, duration_min, created_at) VALUES (?, 'close', 'rule', NULL, ?)""", (field["id"], now_text))
    return decisions
