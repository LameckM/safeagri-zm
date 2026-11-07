import asyncio
import contextlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import auth
from .db import get_conn, init_db
from .scheduler import run_schedule, sync_node_alerts
from .schemas import FieldUpdate, LoginIn, ReadingIn, ReadingOut, RegisterIn
from .validation import check_reading_flags, check_trend_flags, describe_flag

log = logging.getLogger("safeagri")


async def schedule_loop(interval: float):
    """Evaluate every field on a timer so irrigation decisions never wait for a click."""
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(run_schedule)
        except Exception:
            log.exception("Scheduled irrigation check failed")


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
    r"^https?://(localhost|127\.0\.1|"
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


def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = auth.decode_access_token(authorization.split(" ", 1)[1].strip())
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    with get_conn() as conn:
        user = conn.execute(
            """SELECT u.id, u.full_name, u.email, u.farm_id, u.role,
                      f.name AS farm_name, f.location AS farm_location
               FROM users u JOIN farms f ON f.id = u.farm_id WHERE u.id = ?""",
            (user_id,),
        ).fetchone()
    if user is None or user["farm_id"] != payload.get("farm_id"):
        raise HTTPException(status_code=401, detail="Account is no longer available")
    return dict(user)


def require_owned_field(conn, field_id: int, farm_id: int):
    field = conn.execute(
        "SELECT * FROM fields WHERE id = ? AND farm_id = ?", (field_id, farm_id)
    ).fetchone()
    if field is None:
        raise HTTPException(status_code=404, detail="Field not found")
    return field


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", status_code=201)
def register(payload: RegisterIn):
    now = utc_iso()
    with get_conn() as conn:
        existing_users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        if existing_users == 0:
            expected = os.getenv("SAFEAGRI_INITIAL_SETUP_KEY")
            if not expected:
                raise HTTPException(status_code=503, detail="Initial setup is disabled. Configure SAFEAGRI_INITIAL_SETUP_KEY first.")
            if not payload.setup_key or not secrets.compare_digest(payload.setup_key, expected):
                raise HTTPException(status_code=403, detail="A valid initial setup key is required")
        if conn.execute("SELECT id FROM users WHERE email = ?", (payload.email,)).fetchone():
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        farm_cur = conn.execute(
            "INSERT INTO farms (name, location, created_at) VALUES (?, ?, ?)",
            (payload.farm_name, payload.location, now),
        )
        farm_id = farm_cur.lastrowid
        if existing_users == 0:
            # The setup key authorizes the first account to adopt legacy demo data.
            conn.execute("UPDATE fields SET farm_id = ? WHERE farm_id IS NULL", (farm_id,))
        user_cur = conn.execute(
            """INSERT INTO users (farm_id, full_name, email, password_hash, role, created_at)
               VALUES (?, ?, ?, ?, 'farmer', ?)""",
            (farm_id, payload.full_name, payload.email, auth.hash_password(payload.password), now),
        )
    user = {
        "id": user_cur.lastrowid, "full_name": payload.full_name, "email": payload.email,
        "farm_id": farm_id, "farm_name": payload.farm_name,
        "farm_location": payload.location, "role": "farmer",
    }
    return {"access_token": auth.create_access_token(user["id"], farm_id), "token_type": "bearer", "user": user}


@app.post("/auth/login")
def login(payload: LoginIn):
    with get_conn() as conn:
        user = conn.execute(
            """SELECT u.id, u.full_name, u.email, u.password_hash, u.farm_id, u.role,
                      f.name AS farm_name, f.location AS farm_location
               FROM users u JOIN farms f ON f.id = u.farm_id WHERE u.email = ?""",
            (payload.email,),
        ).fetchone()
    if user is None or not auth.verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    public_user = {k: user[k] for k in ("id", "full_name", "email", "farm_id", "farm_name", "farm_location", "role")}
    return {"access_token": auth.create_access_token(user["id"], user["farm_id"]), "token_type": "bearer", "user": public_user}


@app.get("/auth/me")
def get_me(user: dict = Depends(current_user)):
    return user


@app.get("/fields")
def list_fields(user: dict = Depends(current_user)):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM fields WHERE farm_id = ? ORDER BY id", (user["farm_id"],)).fetchall()
    return [dict(r) for r in rows]


@app.patch("/fields/{field_id}")
def update_field(field_id: int, payload: FieldUpdate, user: dict = Depends(current_user)):
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No field changes supplied")
    assignments = ", ".join(f"{key} = ?" for key in changes)
    with get_conn() as conn:
        require_owned_field(conn, field_id, user["farm_id"])
        conn.execute(f"UPDATE fields SET {assignments} WHERE id = ? AND farm_id = ?", [*changes.values(), field_id, user["farm_id"]])
        row = conn.execute("SELECT * FROM fields WHERE id = ?", (field_id,)).fetchone()
    return dict(row)


@app.post("/readings", response_model=ReadingOut, status_code=201)
def create_reading(payload: ReadingIn):
    # Simulator/device ingestion remains node-ID based for now; add per-node
    # credentials before exposing physical devices to an untrusted network.
    received_at = utc_iso()
    recorded_at = utc_iso(payload.timestamp) if payload.timestamp else received_at
    flags = check_reading_flags(payload.soil_moisture, payload.temperature, payload.humidity)
    with get_conn() as conn:
        field = conn.execute("SELECT id, name FROM fields WHERE node_id = ?", (payload.node_id,)).fetchone()
        if field is None:
            raise HTTPException(status_code=404, detail=f"Unknown node_id: {payload.node_id}")
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
def list_readings(field_id: int | None = None, limit: int = Query(100, ge=1, le=1000), include_invalid: bool = False, user: dict = Depends(current_user)):
    sql = "SELECT r.* FROM readings r JOIN fields f ON f.id = r.field_id WHERE f.farm_id = ?"
    params: list = [user["farm_id"]]
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


@app.get("/latest")
def latest_per_field(user: dict = Depends(current_user)):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT f.id AS field_id, f.name AS field_name,
                      r.id, r.soil_moisture, r.temperature, r.humidity,
                      r.recorded_at, r.received_at, r.valid, r.flag,
                      (SELECT MAX(x.received_at) FROM readings x WHERE x.field_id = f.id) AS last_seen_at,
                      (SELECT x.valid FROM readings x WHERE x.field_id = f.id ORDER BY x.received_at DESC, x.id DESC LIMIT 1) AS last_packet_valid
               FROM fields f
               LEFT JOIN readings r ON r.id = (SELECT MAX(v.id) FROM readings v WHERE v.field_id = f.id AND v.valid = 1)
               WHERE f.farm_id = ? ORDER BY f.id""",
            (user["farm_id"],),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/alerts/sync")
def synchronize_alerts():
    sync_node_alerts()
    return {"status": "synced"}


@app.get("/alerts")
def list_alerts(resolved: bool = False, user: dict = Depends(current_user)):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT a.*, f.name AS field_name FROM alerts a JOIN fields f ON f.id = a.field_id
               WHERE a.resolved = ? AND f.farm_id = ? ORDER BY a.id DESC""",
            (int(resolved), user["farm_id"]),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/schedule/run")
def schedule_run(user: dict = Depends(current_user)):
    return run_schedule(user["farm_id"])


@app.get("/schedule/events")
def schedule_events(limit: int = Query(50, ge=1, le=500), user: dict = Depends(current_user)):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT e.*, f.name AS field_name FROM irrigation_events e JOIN fields f ON f.id = e.field_id
               WHERE f.farm_id = ? ORDER BY e.id DESC LIMIT ?""",
            (user["farm_id"], limit),
        ).fetchall()
    return [dict(r) for r in rows]
