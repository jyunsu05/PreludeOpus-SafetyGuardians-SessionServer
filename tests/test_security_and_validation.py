from __future__ import annotations

import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from app import db, main, queries
from app.backup_db import create_backup
from app.models import CompleteRequest, EventBatchRequest, SessionCreateRequest


def api_fail(status: int, code: str, message: str, request_id: str):
    return main.fail(status, code, message, request_id)


class SecurityAndValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DATA_DIR = Path(self.temp_dir.name)
        db.DB_PATH = db.DATA_DIR / "sessions.db"
        db._initialized = False
        db.init_db()
        queries.create_session(
            {"clientSessionId": "session-owned", "mode": "education"},
            "quest-owner",
            "1.0.0",
            "2026-09-03T00:00:00.000Z",
            "request-create",
            api_fail,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def assert_forbidden(self, callback) -> None:
        with self.assertRaises(HTTPException) as raised:
            callback()
        self.assertEqual(403, raised.exception.status_code)
        self.assertEqual("session_device_mismatch", raised.exception.detail["error"]["code"])

    def test_other_device_cannot_retry_owned_session(self) -> None:
        self.assert_forbidden(
            lambda: queries.create_session(
                {"clientSessionId": "session-owned", "mode": "education"},
                "quest-other",
                "1.0.0",
                "2026-09-03T00:00:01.000Z",
                "request-retry",
                api_fail,
            )
        )

    def test_other_device_cannot_post_or_complete(self) -> None:
        self.assert_forbidden(
            lambda: queries.post_events(
                "session-owned",
                {"batchSeq": 1, "events": []},
                "quest-other",
                "1.0.0",
                "2026-09-03T00:00:01.000Z",
                "request-events",
                api_fail,
            )
        )
        self.assert_forbidden(
            lambda: queries.complete_session(
                "session-owned",
                {"reason": "completed", "result": {"passed": True}},
                "quest-other",
                "1.0.0",
                "2026-09-03T00:00:02.000Z",
                "request-complete",
                api_fail,
            )
        )

    def test_body_device_id_cannot_override_authenticated_device(self) -> None:
        body = SessionCreateRequest(
            clientSessionId="spoof-attempt",
            mode="education",
            deviceId="quest-other",
        )
        with self.assertRaises(HTTPException) as raised:
            main.create_session(body, None, "quest-owner", None, "request-spoof")
        self.assertEqual(403, raised.exception.status_code)

    def test_request_models_reject_invalid_ranges_and_shapes(self) -> None:
        with self.assertRaises(ValidationError):
            EventBatchRequest(batchSeq=0, events=[])
        with self.assertRaises(ValidationError):
            EventBatchRequest(batchSeq=1, events=[{"t": -1}])
        with self.assertRaises(ValidationError):
            CompleteRequest(result={"durationSec": -1})
        with self.assertRaises(ValidationError):
            SessionCreateRequest(clientSessionId="", mode="education")

    def test_admin_token_is_optional_locally_and_enforced_when_set(self) -> None:
        original = main.ADMIN_TOKEN
        try:
            main.ADMIN_TOKEN = "secret"
            with self.assertRaises(HTTPException) as raised:
                main.authorize_admin(None, "request-admin")
            self.assertEqual(401, raised.exception.status_code)
            main.authorize_admin("Bearer secret", "request-admin")
        finally:
            main.ADMIN_TOKEN = original

    def test_backup_is_consistent(self) -> None:
        destination = create_backup(db.DB_PATH, Path(self.temp_dir.name) / "backups")
        self.assertTrue(destination.exists())
        import sqlite3

        with closing(sqlite3.connect(destination)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        self.assertEqual(1, count)
        self.assertEqual("ok", integrity)


if __name__ == "__main__":
    unittest.main()
