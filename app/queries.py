from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException
from fastapi.responses import Response

from .db import connect
from .profiles import profile_for

Fail = Callable[[int, str, str, str], HTTPException]


def touch_device(device_id: str, session_id: str | None, app_version: str | None, now: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO devices(device_id, last_seen_at, last_session_id, app_version)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                last_session_id = COALESCE(excluded.last_session_id, devices.last_session_id),
                app_version = COALESCE(excluded.app_version, devices.app_version)
            """,
            (device_id, now, session_id, app_version),
        )


def session_row(session_id: str):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()


def session_response(row) -> dict[str, Any]:
    stored = {}
    if row["rules_json"]:
        try:
            stored = json.loads(row["rules_json"])
        except json.JSONDecodeError:
            stored = {}
    rules = stored.get("rules") or profile_for(row["mode"])[0]
    upload = stored.get("upload") or profile_for(row["mode"])[1]
    payload = {
        "sessionId": row["session_id"],
        "mode": row["mode"],
        "scenarioId": row["scenario_id"],
        "rules": rules,
        "upload": upload,
    }
    if row["trainee_id"]:
        payload["trainee"] = {"id": row["trainee_id"]}
    return payload


def create_session(
    body: dict[str, Any],
    device_id: str,
    content_version: str | None,
    now: str,
    rid: str,
    fail: Fail,
):
    mode = (body.get("mode") or "education").strip()
    if mode not in ("education", "experience"):
        raise fail(400, "unknown_mode", f"mode={mode}", rid)

    client_session_id = (body.get("clientSessionId") or "").strip()
    if not client_session_id:
        raise fail(400, "invalid_json", "clientSessionId required", rid)

    existing = session_row(client_session_id)
    if existing:
        touch_device(device_id, client_session_id, body.get("contentVersion") or content_version, now)
        from fastapi.responses import JSONResponse

        return JSONResponse(session_response(existing), status_code=200)

    trainee_id = body.get("traineeId")
    if isinstance(trainee_id, str):
        trainee_id = trainee_id.strip() or None
    else:
        trainee_id = None

    rules, upload = profile_for(mode)
    scenario_id = body.get("scenarioId") or "hno3_leak_indoor_tank"
    payload = {
        "sessionId": client_session_id,
        "mode": mode,
        "scenarioId": scenario_id,
        "rules": rules,
        "upload": upload,
    }
    if trainee_id:
        payload["trainee"] = {"id": trainee_id}

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions(
                session_id, mode, device_id, trainee_id, course_id, scenario_id,
                content_version, rules_json, status, started_at, received_started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                client_session_id,
                mode,
                body.get("deviceId") or device_id,
                trainee_id,
                body.get("courseId"),
                scenario_id,
                body.get("contentVersion") or content_version,
                json.dumps({"rules": rules, "upload": upload}, ensure_ascii=False),
                body.get("startedAt") or now,
                now,
            ),
        )

    touch_device(
        body.get("deviceId") or device_id,
        client_session_id,
        body.get("contentVersion") or content_version,
        now,
    )
    from fastapi.responses import JSONResponse

    return JSONResponse(payload, status_code=201)


def post_events(
    session_id: str,
    body: dict[str, Any],
    device_id: str,
    content_version: str | None,
    now: str,
    rid: str,
    fail: Fail,
):
    row = session_row(session_id)
    if row is None:
        raise fail(404, "session_not_found", session_id, rid)
    if row["status"] == "completed":
        raise fail(409, "session_already_completed", session_id, rid)

    try:
        batch_seq = int(body.get("batchSeq") or 0)
    except (TypeError, ValueError) as exc:
        raise fail(400, "invalid_json", "batchSeq must be an integer", rid) from exc
    if batch_seq < 1:
        raise fail(400, "invalid_json", "batchSeq must be >= 1", rid)

    events = body.get("events") or []
    if not isinstance(events, list):
        raise fail(400, "invalid_json", "events must be an array", rid)
    if len(json.dumps(events)) > 256 * 1024:
        raise fail(413, "payload_too_large", "events batch too large", rid)

    with connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM session_batches WHERE session_id = ? AND batch_seq = ?",
            (session_id, batch_seq),
        ).fetchone()
        if existing:
            last = conn.execute(
                "SELECT MAX(t) AS last_t FROM session_events WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return {
                "accepted": 0,
                "duplicate": True,
                "lastT": last["last_t"] if last else None,
            }

        conn.execute(
            "INSERT INTO session_batches(session_id, batch_seq, sent_at) VALUES (?, ?, ?)",
            (session_id, batch_seq, body.get("sentAt") or now),
        )
        last_t = None
        last_phase = None
        last_step = None
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            t_value = event.get("t")
            conn.execute(
                """
                INSERT INTO session_events(
                    session_id, batch_seq, event_index, t, at, received_at,
                    type, phase, step, code, severity, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    batch_seq,
                    index,
                    t_value,
                    event.get("at"),
                    now,
                    event.get("type"),
                    event.get("phase"),
                    event.get("step"),
                    event.get("code"),
                    event.get("severity"),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            if t_value is not None:
                last_t = t_value
            if event.get("phase"):
                last_phase = event.get("phase")
            step = event.get("step")
            if not step and isinstance(payload, dict):
                step = payload.get("step")
            if step:
                last_step = step

        if last_phase or last_step:
            conn.execute(
                """
                UPDATE sessions
                SET reached_phase = COALESCE(?, reached_phase),
                    reached_step = COALESCE(?, reached_step)
                WHERE session_id = ?
                """,
                (last_phase, last_step, session_id),
            )

    touch_device(device_id, session_id, content_version, now)
    return {"accepted": len(events), "duplicate": False, "lastT": last_t}


def complete_session(
    session_id: str,
    body: dict[str, Any],
    device_id: str,
    content_version: str | None,
    now: str,
    rid: str,
    fail: Fail,
):
    row = session_row(session_id)
    if row is None:
        raise fail(404, "session_not_found", session_id, rid)
    if row["status"] == "completed":
        return {"sessionId": session_id, "duplicate": True, "status": "completed"}

    result = body.get("result") if isinstance(body.get("result"), dict) else {}
    with connect() as conn:
        conn.execute(
            """
            UPDATE sessions SET
                status = 'completed',
                end_reason = ?,
                passed = ?,
                ended_at = ?,
                duration_sec = ?,
                reached_phase = ?,
                reached_step = ?,
                result_json = ?,
                blocking_violations = ?,
                warn_violations = ?
            WHERE session_id = ?
            """,
            (
                body.get("reason"),
                1 if result.get("passed") else 0,
                body.get("endedAt") or now,
                result.get("durationSec"),
                result.get("reachedPhase"),
                result.get("reachedStep"),
                json.dumps(body, ensure_ascii=False),
                int(result.get("blockingViolations") or 0),
                int(result.get("warnViolations") or 0),
                session_id,
            ),
        )

    touch_device(device_id, session_id, content_version, now)
    return {"sessionId": session_id, "duplicate": False, "status": "completed"}


def list_sessions(
    mode: str | None,
    course_id: str | None,
    passed: bool | None,
    device_id: str | None,
    date: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    clauses = []
    args: list[Any] = []
    if mode:
        clauses.append("mode = ?")
        args.append(mode)
    if course_id:
        clauses.append("course_id = ?")
        args.append(course_id)
    if passed is not None:
        clauses.append("passed = ?")
        args.append(1 if passed else 0)
    if device_id:
        clauses.append("device_id = ?")
        args.append(device_id)
    if date:
        clauses.append("substr(COALESCE(started_at, received_started_at), 1, 10) = ?")
        args.append(date)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT session_id, mode, device_id, trainee_id, course_id, scenario_id,
                   status, end_reason, passed, started_at, ended_at, duration_sec,
                   reached_phase, reached_step, blocking_violations, warn_violations
            FROM sessions{where}
            ORDER BY COALESCE(started_at, received_started_at) DESC
            LIMIT ?
            """,
            [*args, max(1, min(limit, 1000))],
        ).fetchall()
    return [dict(row) for row in rows]


def get_session(session_id: str) -> dict[str, Any] | None:
    row = session_row(session_id)
    if row is None:
        return None
    with connect() as conn:
        events = conn.execute(
            """
            SELECT t, at, received_at, type, phase, step, code, severity, payload_json
            FROM session_events
            WHERE session_id = ?
            ORDER BY t ASC, batch_seq ASC, event_index ASC
            """,
            (session_id,),
        ).fetchall()
    payload = dict(row)
    if payload.get("rules_json"):
        try:
            payload["rules"] = json.loads(payload.pop("rules_json"))
        except json.JSONDecodeError:
            payload["rules"] = payload.pop("rules_json")
    else:
        payload.pop("rules_json", None)
    if payload.get("result_json"):
        try:
            payload["result"] = json.loads(payload.pop("result_json"))
        except json.JSONDecodeError:
            payload["result"] = payload.pop("result_json")
    else:
        payload.pop("result_json", None)
    timeline = []
    for event in events:
        item = dict(event)
        try:
            item["payload"] = json.loads(item.pop("payload_json") or "{}")
        except json.JSONDecodeError:
            item["payload"] = item.pop("payload_json")
        timeline.append(item)
    payload["events"] = timeline
    return payload


def download_jsonl(session_id: str) -> Response:
    if session_row(session_id) is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    with connect() as conn:
        events = conn.execute(
            """
            SELECT t, at, type, phase, step, code, severity, payload_json
            FROM session_events
            WHERE session_id = ?
            ORDER BY t ASC, batch_seq ASC, event_index ASC
            """,
            (session_id,),
        ).fetchall()
    lines = []
    for event in events:
        item = {
            "t": event["t"],
            "at": event["at"],
            "type": event["type"],
            "phase": event["phase"],
            "step": event["step"],
            "code": event["code"],
            "severity": event["severity"],
        }
        try:
            item["payload"] = json.loads(event["payload_json"] or "{}")
        except json.JSONDecodeError:
            item["payload"] = {}
        lines.append(json.dumps(item, ensure_ascii=False))
    body = "\n".join(lines) + ("\n" if lines else "")
    return Response(
        content=body,
        media_type="application/jsonl",
        headers={"Content-Disposition": f'attachment; filename="{session_id}.jsonl"'},
    )


def export_csv(mode: str | None, date: str | None) -> Response:
    clauses = []
    args: list[Any] = []
    if mode:
        clauses.append("mode = ?")
        args.append(mode)
    if date:
        clauses.append("substr(COALESCE(started_at, received_started_at), 1, 10) = ?")
        args.append(date)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT session_id, mode, trainee_id, course_id, device_id, status,
                   end_reason, passed, duration_sec, reached_phase, reached_step,
                   blocking_violations, warn_violations, started_at, ended_at
            FROM sessions{where}
            ORDER BY COALESCE(started_at, received_started_at) DESC
            """,
            args,
        ).fetchall()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "sessionId",
            "mode",
            "traineeId",
            "courseId",
            "deviceId",
            "status",
            "reason",
            "passed",
            "duration",
            "reachedPhase",
            "reachedStep",
            "blockingViolations",
            "warnViolations",
            "startedAt",
            "endedAt",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["session_id"],
                row["mode"],
                row["trainee_id"] or "",
                row["course_id"] or "",
                row["device_id"] or "",
                row["status"],
                row["end_reason"] or "",
                "" if row["passed"] is None else int(row["passed"]),
                row["duration_sec"] if row["duration_sec"] is not None else "",
                row["reached_phase"] or "",
                row["reached_step"] or "",
                row["blocking_violations"] or 0,
                row["warn_violations"] or 0,
                row["started_at"] or "",
                row["ended_at"] or "",
            ]
        )
    filename = f"sessions-{date or 'all'}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def daily_stats(mode: str, date: str | None) -> dict[str, Any]:
    day = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT status, end_reason, duration_sec, reached_step, passed, device_id
            FROM sessions
            WHERE mode = ?
              AND substr(COALESCE(started_at, received_started_at), 1, 10) = ?
            """,
            (mode, day),
        ).fetchall()
        devices = conn.execute(
            """
            SELECT device_id, last_seen_at, last_session_id, app_version
            FROM devices
            ORDER BY last_seen_at DESC
            """
        ).fetchall()

    started = len(rows)
    completed = sum(1 for row in rows if row["end_reason"] == "completed")
    timeouts = sum(1 for row in rows if row["end_reason"] == "timeout")
    passed = sum(1 for row in rows if row["passed"] == 1)
    durations = [row["duration_sec"] for row in rows if row["duration_sec"] is not None]
    drop_counts: dict[str, int] = {}
    for row in rows:
        if row["end_reason"] in ("timeout", "quit", "abandoned") and row["reached_step"]:
            drop_counts[row["reached_step"]] = drop_counts.get(row["reached_step"], 0) + 1
    drop_top = sorted(drop_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
    return {
        "date": day,
        "mode": mode,
        "started": started,
        "completed": completed,
        "timeout": timeouts,
        "passed": passed,
        "averageDurationSec": round(sum(durations) / len(durations), 1) if durations else 0,
        "dropSteps": [{"step": step, "count": count} for step, count in drop_top],
        "devices": [dict(row) for row in devices],
    }


def list_devices() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT device_id, last_seen_at, last_session_id, app_version FROM devices ORDER BY last_seen_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]
