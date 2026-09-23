"""Rule-based irrigation scheduler.

No ML here on purpose. This is the baseline every field gets irrigated
against right now, and it's also the baseline the ML model has to beat
later before it earns a place in the project.

Logic, in order, per field:
  1. No reading at all, or the latest reading is older than STALE_MINUTES:
     treat the node as offline. Do nothing, raise an alert.
  2. Moisture at or above WET_THRESHOLD: skip. Never irrigate soil that's
     already wet, even if something else asked for it.
  3. Moisture at or below DRY_THRESHOLD: irrigate. Duration scales with
     how far below TARGET_MOISTURE the field is, capped at MAX_DURATION_MIN.
  4. Anything in between: skip, moisture is fine.
"""
from datetime import datetime, timedelta, timezone

from .db import get_conn

DRY_THRESHOLD = 25.0       # percent; at or below this, irrigation is needed
WET_THRESHOLD = 60.0       # percent; at or above this, never irrigate
TARGET_MOISTURE = 45.0     # percent; what a irrigation run aims to reach
STALE_MINUTES = 15         # no reading this recent means the node is offline
MIN_DURATION_MIN = 5
MAX_DURATION_MIN = 30
MINUTES_PER_PERCENT = 1.0  # how many minutes of watering per % moisture needed


def _duration_for(current_moisture: float) -> int:
    gap = TARGET_MOISTURE - current_moisture
    minutes = round(gap * MINUTES_PER_PERCENT)
    return max(MIN_DURATION_MIN, min(MAX_DURATION_MIN, minutes))


def evaluate_field(conn, field_row) -> dict:
    field_id = field_row["id"]
    latest = conn.execute(
        """SELECT * FROM readings
           WHERE field_id = ? AND valid = 1
           ORDER BY recorded_at DESC, id DESC LIMIT 1""",
        (field_id,),
    ).fetchone()

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

    recorded_at = datetime.fromisoformat(latest["recorded_at"])
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - recorded_at
    decision["moisture"] = latest["soil_moisture"]

    if age > timedelta(minutes=STALE_MINUTES):
        decision["reason"] = "node_offline"
        return decision

    moisture = latest["soil_moisture"]
    if moisture >= WET_THRESHOLD:
        decision["reason"] = "soil_already_wet"
        return decision

    if moisture <= DRY_THRESHOLD:
        decision["action"] = "irrigate"
        decision["reason"] = "soil_below_dry_threshold"
        decision["duration_min"] = _duration_for(moisture)
        return decision

    decision["reason"] = "moisture_within_range"
    return decision


def run_schedule() -> list[dict]:
    """Evaluate every field, log irrigate decisions as irrigation_events,
    raise a node_offline alert where relevant, and return every decision."""
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    decisions = []

    with get_conn() as conn:
        fields = conn.execute("SELECT * FROM fields ORDER BY id").fetchall()
        for field_row in fields:
            decision = evaluate_field(conn, field_row)
            decisions.append(decision)

            if decision["action"] == "irrigate":
                conn.execute(
                    """INSERT INTO irrigation_events
                       (field_id, action, source, duration_min, created_at)
                       VALUES (?, 'open', 'rule', ?, ?)""",
                    (decision["field_id"], decision["duration_min"], now),
                )
            elif decision["reason"] == "node_offline":
                existing = conn.execute(
                    "SELECT id FROM alerts WHERE field_id = ? AND kind = 'node_offline' AND resolved = 0",
                    (decision["field_id"],),
                ).fetchone()
                if existing is None:
                    conn.execute(
                        "INSERT INTO alerts (field_id, kind, message, created_at) VALUES (?, ?, ?, ?)",
                        (
                            decision["field_id"],
                            "node_offline",
                            f"{decision['field_name']}: no reading in over {STALE_MINUTES} minutes",
                            now,
                        ),
                    )

    return decisions
