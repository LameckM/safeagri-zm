"""Rule-based irrigation scheduler and synchronized alert state."""
import os
from datetime import datetime, timedelta, timezone

from .db import get_conn

DRY_THRESHOLD, WET_THRESHOLD, TARGET_MOISTURE = 25.0, 60.0, 45.0
# Production/demo default remains 15 minutes. Lower this only for accelerated
# simulator tests, e.g. SAFEAGRI_STALE_MINUTES=0.01.
STALE_MINUTES = float(os.getenv("SAFEAGRI_STALE_MINUTES", "15"))
MIN_DURATION_MIN, MAX_DURATION_MIN = 5, 30


def _latest_packet(conn, field_id):
    return conn.execute(
        "SELECT * FROM readings WHERE field_id = ? ORDER BY received_at DESC, id DESC LIMIT 1",
        (field_id,),
    ).fetchone()


def _is_stale(received_at, now):
    stamp = datetime.fromisoformat(received_at)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return now - stamp > timedelta(minutes=STALE_MINUTES)


def evaluate_field(conn, field_row):
    latest = _latest_packet(conn, field_row["id"])
    decision = {
        "field_id": field_row["id"],
        "field_name": field_row["name"],
        "action": "skip",
        "reason": None,
        "duration_min": None,
        "moisture": None,
    }
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
        decision["duration_min"] = max(
            MIN_DURATION_MIN,
            min(MAX_DURATION_MIN, round(TARGET_MOISTURE - moisture)),
        )
    else:
        decision["reason"] = "moisture_within_range"
    return decision


def _sync_alert(conn, field_id, kind, active, message, now_text):
    row = conn.execute(
        "SELECT id FROM alerts WHERE field_id = ? AND kind = ? AND resolved = 0",
        (field_id, kind),
    ).fetchone()
    if active and row:
        conn.execute("UPDATE alerts SET message = ? WHERE id = ?", (message, row["id"]))
    elif active:
        conn.execute(
            "INSERT INTO alerts (field_id, kind, message, created_at) VALUES (?, ?, ?, ?)",
            (field_id, kind, message, now_text),
        )
    elif row:
        conn.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (row["id"],))


def sync_node_alerts():
    now = datetime.now(timezone.utc)
    now_text = now.isoformat(timespec="milliseconds")
    with get_conn() as conn:
        for field in conn.execute("SELECT * FROM fields ORDER BY id").fetchall():
            latest = _latest_packet(conn, field["id"])
            if latest is None:
                continue
            stale = _is_stale(latest["received_at"], now)
            _sync_alert(
                conn, field["id"], "node_offline", stale,
                f"{field['name']}: no sensor packet received in over {STALE_MINUTES:g} minutes",
                now_text,
            )
            dry = not stale and bool(latest["valid"]) and latest["soil_moisture"] <= DRY_THRESHOLD
            _sync_alert(
                conn, field["id"], "dry_soil", dry,
                f"{field['name']}: soil moisture is low ({latest['soil_moisture']}%). Irrigation is recommended.",
                now_text,
            )


def run_schedule():
    sync_node_alerts()
    now_text = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    decisions = []
    with get_conn() as conn:
        for field in conn.execute("SELECT * FROM fields ORDER BY id").fetchall():
            decision = evaluate_field(conn, field)
            decisions.append(decision)
            last = conn.execute(
                "SELECT action FROM irrigation_events WHERE field_id = ? ORDER BY id DESC LIMIT 1",
                (field["id"],),
            ).fetchone()
            if decision["action"] == "irrigate" and (last is None or last["action"] != "open"):
                conn.execute(
                    """INSERT INTO irrigation_events
                       (field_id, action, source, duration_min, created_at)
                       VALUES (?, 'open', 'rule', ?, ?)""",
                    (field["id"], decision["duration_min"], now_text),
                )
            elif decision["action"] != "irrigate" and last is not None and last["action"] == "open":
                conn.execute(
                    """INSERT INTO irrigation_events
                       (field_id, action, source, duration_min, created_at)
                       VALUES (?, 'close', 'rule', NULL, ?)""",
                    (field["id"], now_text),
                )
    return decisions
