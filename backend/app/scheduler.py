"""Rule-based irrigation scheduler and synchronized alert state."""
from datetime import datetime, timedelta, timezone
from .db import get_conn

DRY_THRESHOLD, WET_THRESHOLD, TARGET_MOISTURE = 25.0, 60.0, 45.0
STALE_MINUTES, MIN_DURATION_MIN, MAX_DURATION_MIN = 15, 5, 30

def _latest_packet(conn, field_id):
    return conn.execute("SELECT * FROM readings WHERE field_id = ? ORDER BY received_at DESC, id DESC LIMIT 1", (field_id,)).fetchone()

def _is_stale(received_at, now):
    stamp = datetime.fromisoformat(received_at)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return now - stamp > timedelta(minutes=STALE_MINUTES)

def evaluate_field(conn, field_row):
    latest = _latest_packet(conn, field_row["id"])
    d = {"field_id": field_row["id"], "field_name": field_row["name"], "action": "skip", "reason": None, "duration_min": None, "moisture": None}
    if latest is None:
        d["reason"] = "no_readings_yet"; return d
    if _is_stale(latest["received_at"], datetime.now(timezone.utc)):
        d["reason"] = "node_offline"; return d
    if not latest["valid"]:
        d["reason"] = "sensor_fault"; return d
    moisture = latest["soil_moisture"]; d["moisture"] = moisture
    if moisture >= WET_THRESHOLD: d["reason"] = "soil_already_wet"
    elif moisture <= DRY_THRESHOLD:
        d["action"] = "irrigate"; d["reason"] = "soil_below_dry_threshold"
        d["duration_min"] = max(MIN_DURATION_MIN, min(MAX_DURATION_MIN, round(TARGET_MOISTURE - moisture)))
    else: d["reason"] = "moisture_within_range"
    return d

def _sync_alert(conn, field_id, kind, active, message, now_text):
    row = conn.execute("SELECT id FROM alerts WHERE field_id = ? AND kind = ? AND resolved = 0", (field_id, kind)).fetchone()
    if active and row:
        conn.execute("UPDATE alerts SET message = ? WHERE id = ?", (message, row["id"]))
    elif active:
        conn.execute("INSERT INTO alerts (field_id, kind, message, created_at) VALUES (?, ?, ?, ?)", (field_id, kind, message, now_text))
    elif row:
        conn.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (row["id"],))

def sync_node_alerts():
    now = datetime.now(timezone.utc); now_text = now.isoformat(timespec="milliseconds")
    with get_conn() as conn:
        for field in conn.execute("SELECT * FROM fields ORDER BY id").fetchall():
            latest = _latest_packet(conn, field["id"])
            if latest is None: continue
            stale = _is_stale(latest["received_at"], now)
            _sync_alert(conn, field["id"], "node_offline", stale,
                f"{field['name']}: no sensor packet received in over {STALE_MINUTES} minutes", now_text)
            dry = not stale and bool(latest["valid"]) and latest["soil_moisture"] <= DRY_THRESHOLD
            _sync_alert(conn, field["id"], "dry_soil", dry,
                f"{field['name']}: soil moisture is low ({latest['soil_moisture']}%). Irrigation is recommended.", now_text)

def run_schedule():
    sync_node_alerts()
    now_text = datetime.now(timezone.utc).isoformat(timespec="milliseconds"); decisions = []
    with get_conn() as conn:
        for field in conn.execute("SELECT * FROM fields ORDER BY id").fetchall():
            d = evaluate_field(conn, field); decisions.append(d)
            last = conn.execute("SELECT action FROM irrigation_events WHERE field_id = ? ORDER BY id DESC LIMIT 1", (field["id"],)).fetchone()
            if d["action"] == "irrigate" and (last is None or last["action"] != "open"):
                conn.execute("INSERT INTO irrigation_events (field_id, action, source, duration_min, created_at) VALUES (?, 'open', 'rule', ?, ?)", (field["id"], d["duration_min"], now_text))
            elif d["action"] != "irrigate" and last is not None and last["action"] == "open":
                conn.execute("INSERT INTO irrigation_events (field_id, action, source, duration_min, created_at) VALUES (?, 'close', 'rule', NULL, ?)", (field["id"], now_text))
    return decisions
