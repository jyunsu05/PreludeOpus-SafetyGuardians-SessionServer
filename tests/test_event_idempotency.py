from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app import db, queries


def fail(status: int, code: str, message: str, request_id: str):
    raise AssertionError((status, code, message, request_id))


class EventIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DATA_DIR = Path(self.temp_dir.name)
        db.DB_PATH = db.DATA_DIR / "sessions.db"
        db._initialized = False
        db.init_db()
        queries.create_session(
            {
                "clientSessionId": "session-1",
                "mode": "education",
                "scenarioId": "hno3_leak_indoor_tank",
            },
            "quest-1",
            "1.0.0",
            "2026-08-31T00:00:00.000Z",
            "request-1",
            fail,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def event(event_id: str, t: float) -> dict:
        return {
            "eventId": event_id,
            "t": t,
            "at": "2026-08-31T00:00:00.000Z",
            "type": "violation",
            "phase": "Containment",
            "code": "contain_before_valve",
            "severity": "block",
            "payload": {"attempt": "deploy_boom"},
        }

    def post(self, batch_seq: int, events: list[dict]) -> dict:
        return queries.post_events(
            "session-1",
            {"batchSeq": batch_seq, "events": events},
            "quest-1",
            "1.0.0",
            "2026-08-31T00:00:01.000Z",
            f"request-{batch_seq}",
            fail,
        )

    def test_distinct_occurrences_with_same_code_are_preserved(self) -> None:
        result = self.post(1, [self.event("event-1", 1.0), self.event("event-2", 2.0)])
        self.assertEqual(2, result["accepted"])
        self.assertEqual(0, result["duplicateEvents"])

        with db.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM session_events").fetchone()[0]
        self.assertEqual(2, count)

    def test_repeated_session_start_returns_the_existing_session(self) -> None:
        response = queries.create_session(
            {"clientSessionId": "session-1", "mode": "education"},
            "quest-1",
            "1.0.0",
            "2026-08-31T00:00:02.000Z",
            "request-retry",
            fail,
        )

        self.assertEqual(200, response.status_code)
        with db.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        self.assertEqual(1, count)

    def test_event_retry_in_a_new_batch_is_not_stored_twice(self) -> None:
        self.post(1, [self.event("event-1", 1.0)])
        result = self.post(2, [self.event("event-1", 1.0), self.event("event-2", 2.0)])

        self.assertEqual(1, result["accepted"])
        self.assertEqual(1, result["duplicateEvents"])
        with db.connect() as conn:
            ids = [
                row["event_id"]
                for row in conn.execute(
                    "SELECT event_id FROM session_events ORDER BY t"
                ).fetchall()
            ]
        self.assertEqual(["event-1", "event-2"], ids)

    def test_existing_database_is_migrated_without_losing_events(self) -> None:
        legacy_path = db.DATA_DIR / "legacy.db"
        with closing(sqlite3.connect(legacy_path)) as conn, conn:
            conn.execute(
                """
                CREATE TABLE session_events (
                    session_id TEXT NOT NULL,
                    batch_seq INTEGER NOT NULL,
                    event_index INTEGER NOT NULL,
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
                )
                """
            )
            conn.execute(
                "INSERT INTO session_events(session_id, batch_seq, event_index, t) VALUES ('s', 1, 0, 1.0)"
            )

        original_path = db.DB_PATH
        try:
            db.DB_PATH = legacy_path
            db._initialized = False
            db.init_db()
            with db.connect() as conn:
                columns = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(session_events)").fetchall()
                }
                count = conn.execute("SELECT COUNT(*) FROM session_events").fetchone()[0]
            self.assertIn("event_id", columns)
            self.assertEqual(1, count)
        finally:
            db.DB_PATH = original_path
            db._initialized = True


if __name__ == "__main__":
    unittest.main()
