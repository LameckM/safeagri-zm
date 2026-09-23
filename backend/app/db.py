"""SQLite setup for the smart irrigation backend."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", "data/irrigation.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS fields (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    node_id TEXT NOT NULL UNIQUE,
    crop    TEXT NOT NULL DEFAULT 'maize'
);

CREATE TABLE IF NOT EXISTS readings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id      INTEGER NOT NULL REFERENCES fields(id),
    soil_moisture REAL NOT NULL,
    temperature   REAL NOT NULL,
    humidity      REAL NOT NULL,
    recorded_at   TEXT NOT NULL,  -- when the node measured it (UTC ISO)
    received_at   TEXT NOT NULL,  -- when the server got it (UTC ISO)
    valid         INTEGER NOT NULL DEFAULT 1,
    flag          TEXT            -- reason when valid = 0
);
CREATE INDEX IF NOT EXISTS idx_readings_field_time
    ON readings(field_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id   INTEGER NOT NULL REFERENCES fields(id),
    kind       TEXT NOT NULL,     -- e.g. sensor_fault, dry_soil, node_offline
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS irrigation_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id     INTEGER NOT NULL REFERENCES fields(id),
    action       TEXT NOT NULL,   -- open or close
    source       TEXT NOT NULL,   -- rule, ml or manual
    duration_min INTEGER,
    created_at   TEXT NOT NULL
);
"""

# 4 fields, 4 nodes, as agreed in the spec
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


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT OR IGNORE INTO fields (id, name, node_id) VALUES (?, ?, ?)",
            SEED_FIELDS,
        )
