from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .db import get_conn, init_db
from .scheduler import run_schedule
from .schemas import ReadingIn, ReadingOut
from .validation import check_reading_flags


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Smart Irrigation API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def utc_iso(dt: datetime | None = None) -> str:
    """Fixed-width UTC timestamp so string sorting matches time sorting."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/fields")
def list_fields():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM fields ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.post("/readings", response_model=ReadingOut, status_code=201)
def create_reading(payload: ReadingIn):
    received_at = utc_iso()
    recorded_at = utc_iso(payload.timestamp) if payload.timestamp else received_at
    flags = check_reading_flags(payload.soil_moisture, payload.temperature, payload.humidity)

    with get_conn() as conn:
        field = conn.execute(
            "SELECT id FROM fields WHERE node_id = ?", (payload.node_id,)
        ).fetchone()
        if field is None:
            raise HTTPException(status_code=404, detail=f"Unknown node_id: {payload.node_id}")

        cur = conn.execute(
            """INSERT INTO readings
               (field_id, soil_moisture, temperature, humidity,
                recorded_at, received_at, valid, flag)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                field["id"], payload.soil_moisture, payload.temperature,
                payload.humidity, recorded_at, received_at,
                0 if flags else 1, ",".join(flags) if flags else None,
            ),
        )

        if flags:
            # One active alert per field. Repeated bad samples update the
            # same alert instead of flooding the dashboard.
            message = (
                f"{field['id']}: " + "; ".join(
                    f"{flag.removesuffix('_out_of_range').replace('_', ' ')} "
                    f"reading {getattr(payload, flag.removesuffix('_out_of_range'))} is out of range"
                    for flag in flags
                )
            )
            existing = conn.execute(
                "SELECT id FROM alerts WHERE field_id = ? AND kind = 'sensor_fault' AND resolved = 0",
                (field["id"],),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE alerts SET message = ?, created_at = ? WHERE id = ?",
                    (message, received_at, existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO alerts (field_id, kind, message, created_at) VALUES (?, 'sensor_fault', ?, ?)",
                    (field["id"], message, received_at),
                )
        else:
            # A fresh valid packet confirms the node and its sensors have
            # recovered. Close their previous active alerts.
            conn.execute(
                """UPDATE alerts SET resolved = 1
                   WHERE field_id = ? AND resolved = 0
                   AND kind IN ('sensor_fault', 'node_offline')""",
                (field["id"],),
            )

    return ReadingOut(
        id=cur.lastrowid, field_id=field["id"],
        valid=not flags, flag=",".join(flags) if flags else None,
    )


@app.get("/readings")
def list_readings(
    field_id: int | None = None,
    limit: int = Query(100, ge=1, le=1000),
    include_invalid: bool = False,
):
    sql = "SELECT * FROM readings WHERE 1=1"
    params: list = []
    if field_id is not None:
        sql += " AND field_id = ?"
        params.append(field_id)
    if not include_invalid:
        sql += " AND valid = 1"
    sql += " ORDER BY recorded_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@app.get("/latest")
def latest_per_field():
    """Newest valid reading for each field. This is what the dashboard polls."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT r.*, f.name AS field_name
               FROM readings r JOIN fields f ON f.id = r.field_id
               WHERE r.id IN (SELECT MAX(id) FROM readings WHERE valid = 1 GROUP BY field_id)
               ORDER BY r.field_id"""
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/alerts")
def list_alerts(resolved: bool = False):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT a.*, f.name AS field_name
               FROM alerts a JOIN fields f ON f.id = a.field_id
               WHERE a.resolved = ? ORDER BY a.id DESC""",
            (int(resolved),),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/schedule/run")
def schedule_run():
    """Evaluate all fields against the rule-based thresholds and act on it."""
    return run_schedule()


@app.get("/schedule/events")
def schedule_events(limit: int = Query(50, ge=1, le=500)):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT e.*, f.name AS field_name FROM irrigation_events e
               JOIN fields f ON f.id = e.field_id
               ORDER BY e.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
