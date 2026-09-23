from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query

from .db import get_conn, init_db
from .schemas import ReadingIn, ReadingOut
from .validation import check_reading


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Smart Irrigation API", lifespan=lifespan)


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
    flag = check_reading(payload.soil_moisture, payload.temperature, payload.humidity)

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
                field["id"],
                payload.soil_moisture,
                payload.temperature,
                payload.humidity,
                recorded_at,
                received_at,
                0 if flag else 1,
                flag,
            ),
        )

        if flag:
            metric = flag.removesuffix("_out_of_range")
            value = getattr(payload, metric)
            conn.execute(
                "INSERT INTO alerts (field_id, kind, message, created_at) VALUES (?, ?, ?, ?)",
                (
                    field["id"],
                    "sensor_fault",
                    f"Field {field['id']}: {metric.replace('_', ' ')} reading {value} is out of range",
                    received_at,
                ),
            )

    return ReadingOut(id=cur.lastrowid, field_id=field["id"], valid=flag is None, flag=flag)


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
            "SELECT * FROM alerts WHERE resolved = ? ORDER BY id DESC", (int(resolved),)
        ).fetchall()
    return [dict(r) for r in rows]
