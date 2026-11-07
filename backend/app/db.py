"""SQLite setup and forward-compatible schema migrations."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", "data/irrigation.db"))

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
CREATE INDEX IF NOT EXISTS idx_users_farm ON users(farm_id);

CREATE TABLE IF NOT EXISTS node_status (
    node_id TEXT PRIMARY KEY,
    online INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
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
