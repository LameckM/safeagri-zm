import asyncio
import contextlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os

from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from . import auth
from .db import get_conn, init_db
from .scheduler import run_schedule, sync_node_alerts
from .schemas import FieldUpdate, ReadingIn, ReadingOut, WaterUsageIn
from .validation import check_reading_flags, check_trend_flags, describe_flag

log = logging.getLogger("safeagri")


async def schedule_loop(interval: float):
    """Evaluate all fields immediately, then repeat without dashboard interaction."""
    while True:
        try:
            # Run once at startup; do not leave fields waiting for the first timer tick.
            await asyncio.to_thread(run_schedule)
        except Exception:
            log.exception("Scheduled irrigation check failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    interval = float(os.getenv("SAFEAGRI_SCHEDULE_SECONDS", "60"))
    task = asyncio.create_task(schedule_loop(interval)) if interval > 0 else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="SafeAgri Smart Irrigation API", lifespan=lifespan)
LOCAL_DASHBOARD_ORIGIN = (
    r"^https?://(localhost|127\.0\.0\.1|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3})"
    r"(:\d+)?$"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=LOCAL_DASHBOARD_ORIGIN,
    allow_methods=["*"],
    allow_headers=["*"],
)


def utc_iso(dt: datetime | None = None) -> str:
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def require_field(conn, field_id: int):
    field = conn.execute("SELECT * FROM fields WHERE id = ?", (field_id,)).fetchone()
    if field is None:
        raise HTTPException(status_code=404, detail="Field not found")
    return field



@app.get("/health")
def health():
    return {"status": "ok"}


# Never SELECT * from fields in a response: node_key_hash must not leave the server.
PUBLIC_FIELD_COLUMNS = "id, name, node_id, crop, (node_key_hash IS NOT NULL) AS has_node_key"


def public_field(row) -> dict:
    field = dict(row)
    field["has_node_key"] = bool(field["has_node_key"])
    return field


@app.get("/fields")
def list_fields():
    with get_conn() as conn:
        rows = conn.execute(f"SELECT {PUBLIC_FIELD_COLUMNS} FROM fields ORDER BY id").fetchall()
    return [public_field(r) for r in rows]


@app.post("/fields/{field_id}/node-key")
def issue_node_key(field_id: int, response: Response):
    """Issue (or rotate) the credential a sensor node sends in the X-Node-Key header.

    The key is returned once and only its hash is stored. Issuing a new key
    immediately stops the previous one.
    """
    key = auth.generate_node_key()
    with get_conn() as conn:
        field = require_field(conn, field_id)
        conn.execute("UPDATE fields SET node_key_hash = ? WHERE id = ?", (auth.hash_node_key(key), field_id))
    response.headers["Cache-Control"] = "no-store"
    return {"field_id": field_id, "node_id": field["node_id"], "node_key": key}


@app.patch("/fields/{field_id}")
def update_field(field_id: int, payload: FieldUpdate):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No field changes supplied")
    assignments = ", ".join(f"{key} = ?" for key in changes)
    with get_conn() as conn:
        require_field(conn, field_id)
        conn.execute(f"UPDATE fields SET {assignments} WHERE id = ?", [*changes.values(), field_id])
        row = conn.execute(f"SELECT {PUBLIC_FIELD_COLUMNS} FROM fields WHERE id = ?", (field_id,)).fetchone()
    return public_field(row)


@app.post("/readings", response_model=ReadingOut, status_code=201)
def create_reading(payload: ReadingIn, x_node_key: str | None = Header(default=None)):
    received_at = utc_iso()
    recorded_at = utc_iso(payload.timestamp) if payload.timestamp else received_at
    flags = check_reading_flags(payload.soil_moisture, payload.temperature, payload.humidity)
    with get_conn() as conn:
        field = conn.execute(
            "SELECT id, name, node_key_hash FROM fields WHERE node_id = ?", (payload.node_id,)
        ).fetchone()
        stored_hash = field["node_key_hash"] if field else None
        if not auth.node_key_matches(x_node_key, stored_hash):
            # One answer for unknown node, no key issued, and wrong key, so the
            # API does not reveal which node IDs exist. The log says which it was.
            reason = "unknown node" if field is None else "no key issued" if stored_hash is None else "wrong or missing key"
            log.warning("Reading rejected for node %r: %s", payload.node_id, reason)
            raise HTTPException(status_code=401, detail="Invalid node credentials")
        recent = conn.execute(
            "SELECT soil_moisture FROM readings WHERE field_id = ? ORDER BY id DESC LIMIT 10",
            (field["id"],),
        ).fetchall()
        last_ok = conn.execute(
            """SELECT soil_moisture, recorded_at FROM readings
               WHERE field_id = ? AND soil_moisture BETWEEN 0 AND 100
               ORDER BY id DESC LIMIT 1""",
            (field["id"],),
        ).fetchone()
        flags += check_trend_flags(
            payload.soil_moisture,
            recorded_at,
            [row["soil_moisture"] for row in recent],
            (last_ok["soil_moisture"], last_ok["recorded_at"]) if last_ok else None,
        )
        cur = conn.execute(
            """INSERT INTO readings
               (field_id, soil_moisture, temperature, humidity, recorded_at, received_at, valid, flag)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (field["id"], payload.soil_moisture, payload.temperature, payload.humidity, recorded_at, received_at, 0 if flags else 1, ",".join(flags) if flags else None),
        )
        if flags:
            message = f"{field['name']}: " + "; ".join(
                describe_flag(flag, payload.soil_moisture, payload.temperature, payload.humidity)
                for flag in flags
            )
            existing = conn.execute("SELECT id FROM alerts WHERE field_id = ? AND kind = 'sensor_fault' AND resolved = 0", (field["id"],)).fetchone()
            if existing:
                conn.execute("UPDATE alerts SET message = ? WHERE id = ?", (message, existing["id"]))
            else:
                conn.execute("INSERT INTO alerts (field_id, kind, message, created_at) VALUES (?, 'sensor_fault', ?, ?)", (field["id"], message, received_at))
        else:
            conn.execute("UPDATE alerts SET resolved = 1 WHERE field_id = ? AND resolved = 0 AND kind = 'sensor_fault'", (field["id"],))
    return ReadingOut(id=cur.lastrowid, field_id=field["id"], valid=not flags, flag=",".join(flags) if flags else None)


@app.get("/readings")
def list_readings(field_id: int | None = None, limit: int = Query(100, ge=1, le=1000), include_invalid: bool = False):
    sql = "SELECT r.* FROM readings r WHERE 1 = 1"
    params: list = []
    if field_id is not None:
        sql += " AND r.field_id = ?"
        params.append(field_id)
    if not include_invalid:
        sql += " AND r.valid = 1"
    sql += " ORDER BY r.recorded_at DESC, r.id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@app.post("/water-usage", status_code=201)
def create_water_usage(payload: WaterUsageIn, x_node_key: str | None = Header(default=None)):
    recorded_at = utc_iso(payload.timestamp) if payload.timestamp else utc_iso()
    received_at = utc_iso()
    with get_conn() as conn:
        field = conn.execute(
            "SELECT id, node_key_hash FROM fields WHERE node_id = ?", (payload.node_id,)
        ).fetchone()
        stored_hash = field["node_key_hash"] if field else None
        if not auth.node_key_matches(x_node_key, stored_hash):
            raise HTTPException(status_code=401, detail="Invalid node credentials")
        cur = conn.execute(
            """INSERT INTO water_usage_readings
               (field_id, liters, recorded_at, received_at, source)
               VALUES (?, ?, ?, ?, ?)""",
            (field["id"], payload.liters, recorded_at, received_at, payload.source),
        )
    return {"id": cur.lastrowid, "field_id": field["id"], "liters": payload.liters, "recorded_at": recorded_at}


@app.get("/water-usage")
def list_water_usage(days: int = Query(30, ge=1, le=365), field_id: int | None = None):
    with get_conn() as conn:
        sql = """SELECT w.id, w.field_id, f.name AS field_name, f.node_id,
                        w.liters, w.recorded_at, w.source
                 FROM water_usage_readings w
                 JOIN fields f ON f.id = w.field_id
                 WHERE w.recorded_at >= datetime('now', ?)"""
        params = [f"-{days} days"]
        if field_id is not None:
            sql += " AND w.field_id = ?"
            params.append(field_id)
        sql += " ORDER BY w.recorded_at ASC, w.id ASC"
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


@app.get("/latest")
def latest_per_field():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT f.id AS field_id, f.name AS field_name,
                      r.id, r.soil_moisture, r.temperature, r.humidity,
                      r.recorded_at, r.received_at, r.valid, r.flag,
                      (SELECT MAX(x.received_at) FROM readings x WHERE x.field_id = f.id) AS last_seen_at,
                      (SELECT x.valid FROM readings x WHERE x.field_id = f.id ORDER BY x.received_at DESC, x.id DESC LIMIT 1) AS last_packet_valid
               FROM fields f
               LEFT JOIN readings r ON r.id = (SELECT MAX(v.id) FROM readings v WHERE v.field_id = f.id AND v.valid = 1)
               ORDER BY f.id""",
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/alerts/sync")
def synchronize_alerts():
    sync_node_alerts()
    return {"status": "synced"}


@app.get("/alerts")
def list_alerts(resolved: bool = False):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT a.*, f.name AS field_name FROM alerts a JOIN fields f ON f.id = a.field_id
               WHERE a.resolved = ? ORDER BY a.id DESC""",
            (int(resolved),)
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/schedule/run")
def schedule_run():
    return run_schedule()


@app.get("/schedule/events")
def schedule_events(limit: int = Query(50, ge=1, le=500)):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT e.*, f.name AS field_name FROM irrigation_events e JOIN fields f ON f.id = e.field_id
               ORDER BY e.id DESC LIMIT ?""",
            (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
