"""SQLite setup and forward-compatible schema migrations."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Default to backend/data next to the code, not the current directory, so starting
# uvicorn from the repo root or from backend/ always opens the same database.
# An explicit DB_PATH is used exactly as given.
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "irrigation.db"
DB_PATH = Path(os.getenv("DB_PATH") or DEFAULT_DB_PATH)

SCHEMA = """
CREATE TABLE IF NOT EXISTS farms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL REFERENCES farms(id),
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'farmer',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL REFERENCES farms(id),
    code_hash TEXT NOT NULL UNIQUE,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    used_by INTEGER REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_invites_farm ON invites(farm_id);

CREATE TABLE IF NOT EXISTS fields (
    id INTEGER PRIMARY KEY,
    farm_id INTEGER REFERENCES farms(id),
    name TEXT NOT NULL,
    node_id TEXT NOT NULL UNIQUE,
    crop TEXT NOT NULL DEFAULT 'maize',
    node_key_hash TEXT
);

CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL REFERENCES fields(id),
    soil_moisture REAL NOT NULL,
    temperature REAL NOT NULL,
    humidity REAL NOT NULL,
    recorded_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    valid INTEGER NOT NULL DEFAULT 1,
    flag TEXT
);
CREATE INDEX IF NOT EXISTS idx_readings_field_time
    ON readings(field_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL REFERENCES fields(id),
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS irrigation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL REFERENCES fields(id),
    action TEXT NOT NULL,
    source TEXT NOT NULL,
    duration_min INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS water_usage_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL REFERENCES fields(id),
    liters REAL NOT NULL CHECK (liters >= 0),
    recorded_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'simulated',
    irrigation_event_id INTEGER REFERENCES irrigation_events(id)
);
CREATE INDEX IF NOT EXISTS idx_water_usage_field_time
    ON water_usage_readings(field_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_farm ON users(farm_id);
"""

SEED_FIELDS = [
    (1, "Field 1", "node-01"),
    (2, "Field 2", "node-02"),
    (3, "Field 3", "node-03"),
    (4, "Field 4", "node-04"),
]


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_existing_database(conn: sqlite3.Connection) -> None:
    """Add farm ownership to databases created before multi-farm support."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(fields)")}
    if "farm_id" not in columns:
        conn.execute("ALTER TABLE fields ADD COLUMN farm_id INTEGER REFERENCES farms(id)")
    if "node_key_hash" not in columns:
        conn.execute("ALTER TABLE fields ADD COLUMN node_key_hash TEXT")
    usage_columns = {row["name"] for row in conn.execute("PRAGMA table_info(water_usage_readings)")}
    if "irrigation_event_id" not in usage_columns:
        conn.execute("ALTER TABLE water_usage_readings ADD COLUMN irrigation_event_id INTEGER REFERENCES irrigation_events(id)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_water_usage_event ON water_usage_readings(irrigation_event_id) WHERE irrigation_event_id IS NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fields_farm ON fields(farm_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_farm ON users(farm_id)")


def init_db() -> None:
    with get_conn() as conn:
        # Create parent tables first, then apply the fields ownership migration.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.executescript(SCHEMA)
        _migrate_existing_database(conn)
        conn.executemany(
            "INSERT OR IGNORE INTO fields (id, name, node_id) VALUES (?, ?, ?)",
            SEED_FIELDS,
        )
