from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "sessions.db"

_initialized = False


def _raw_connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    global _initialized
    if not _initialized:
        init_db()
    conn = _raw_connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    global _initialized
    conn = _raw_connect()
    try:
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                token_hash TEXT,
                last_seen_at TEXT,
                last_session_id TEXT,
                app_version TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                device_id TEXT,
                trainee_id TEXT,
                course_id TEXT,
                scenario_id TEXT,
                content_version TEXT,
                rules_json TEXT,
                status TEXT NOT NULL,
                end_reason TEXT,
                passed INTEGER,
                started_at TEXT,
                ended_at TEXT,
                received_started_at TEXT,
                duration_sec REAL,
                reached_phase TEXT,
                reached_step TEXT,
                result_json TEXT,
                blocking_violations INTEGER DEFAULT 0,
                warn_violations INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS session_batches (
                session_id TEXT NOT NULL,
                batch_seq INTEGER NOT NULL,
                sent_at TEXT,
                PRIMARY KEY (session_id, batch_seq)
            );

            CREATE TABLE IF NOT EXISTS session_events (
                session_id TEXT NOT NULL,
                batch_seq INTEGER NOT NULL,
                event_index INTEGER NOT NULL,
                event_id TEXT,
                t REAL,
                at TEXT,
                received_at TEXT,
                type TEXT,
                phase TEXT,
                step TEXT,
                code TEXT,
                severity TEXT,
                payload_json TEXT,
                PRIMARY KEY (session_id, batch_seq, event_index)
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_mode_started
                ON sessions(mode, started_at);
            CREATE INDEX IF NOT EXISTS idx_events_session_t
                ON session_events(session_id, t);
            CREATE INDEX IF NOT EXISTS idx_events_type
                ON session_events(type, code);
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(session_events)").fetchall()
            }
            if "event_id" not in columns:
                conn.execute("ALTER TABLE session_events ADD COLUMN event_id TEXT")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_events_event_id
                    ON session_events(event_id)
                    WHERE event_id IS NOT NULL
                """
            )
    finally:
        conn.close()
    _initialized = True
