"""Rule-based irrigation scheduler and alert freshness synchronization."""
from datetime import datetime, timedelta, timezone

from .db import get_conn

DRY_THRESHOLD = 25.0
WET_THRESHOLD = 60.0
TARGET_MOISTURE = 45.0
STALE_MINUTES = 15
MIN_DURATION_MIN = 5
MAX_DURATION_MIN = 30
MINUTES_PER_PERCENT = 1.0


def _duration_for(current_moisture: float) -> int:
    gap = TARGET_MOISTURE - current_moisture
    return max(MIN_DURATION_MIN, min(MAX_DURATION_MIN, round(gap * MINUTES_PER_PERCENT)))


def _latest_packet(conn, field_id):
    return conn.execute(
        """SELECT * FROM readings WHERE field_id = ?
           ORDER BY received_at DESC, id DESC LIMIT 1""",
        (field_id,),
    ).fetchone()


def evaluate_field(conn, field_row) -> dict:
    field_id = field_row["id"]
    latest = _latest_packet(conn, field_id)
    decision = {
        "field_id": field_id,
        "field_name": field_row["name"],
        "action": "skip",
        "reason": None,
        "duration_min": None,
        "moisture": None,
    }

    if latest is None:
        decision["reason"] = "no_readings_yet"
        return decision

    # received_at is the server clock and is therefore the reliable signal
    # for node liveness even when an ESP32/simulator clock is incorrect.
    received_at = datetime.fromisoformat(latest["received_at"])
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - received_at > timedelta(minutes=STALE_MINUTES):
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
        decision["duration_min"] = _duration_for(moisture)
    else:
        decision["reason"] = "moisture_within_range"
    return decision


def sync_node_alerts() -> None:
    """Create one stale-node alert and resolve it as soon as packets resume."""
    now = datetime.now(timezone.utc)
    with get_conn() as conn:
        fields = conn.execute("SELECT * FROM fields ORDER BY id").fetchall()
        for field in fields:
            latest = _latest_packet(conn, field["id"])
            if latest is None:
                continue  # no data yet is not proof of an outage

            received = datetime.fromisoformat(latest["received_at"])
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
            stale = now - received > timedelta(minutes=STALE_MINUTES)

            active = conn.execute(
                """SELECT id FROM alerts WHERE field_id = ?
                   AND kind = 'node_offline' AND resolved = 0""",
                (field["id"],),
            ).fetchone()

            if stale and active is None:
                conn.execute(
                    """INSERT INTO alerts (field_id, kind, message, created_at)
                       VALUES (?, 'node_offline', ?, ?)""",
                    (field["id"], f"{field['name']}: no sensor packet received in over {STALE_MINUTES} minutes",
                     now.isoformat(timespec="milliseconds")),
                )
            elif not stale and active is not None:
                conn.execute(
                    "UPDATE alerts SET resolved = 1 WHERE id = ?", (active["id"],)
                )


def run_schedule() -> list[dict]:
    """Evaluate fields, record irrigation decisions, and keep offline alerts current."""
    sync_node_alerts()
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    decisions = []

    with get_conn() as conn:
        fields = conn.execute("SELECT * FROM fields ORDER BY id").fetchall()
        for field in fields:
            decision = evaluate_field(conn, field)
            decisions.append(decision)
            if decision["action"] != "irrigate":
                continue

            # Avoid writing duplicate 'open' events every time the dashboard
            # checks while the same field remains dry.
            last_event = conn.execute(
                """SELECT action FROM irrigation_events
                   WHERE field_id = ? ORDER BY id DESC LIMIT 1""",
                (decision["field_id"],),
            ).fetchone()
            if last_event is None or last_event["action"] != "open":
                conn.execute(
                    """INSERT INTO irrigation_events
                       (field_id, action, source, duration_min, created_at)
                       VALUES (?, 'open', 'rule', ?, ?)""",
                    (decision["field_id"], decision["duration_min"], now),
                )
    return decisions
