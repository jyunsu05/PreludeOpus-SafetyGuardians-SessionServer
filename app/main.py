from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from . import queries
from .db import DB_PATH, connect, init_db

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DEV_TOKEN = os.environ.get("DEVICE_TOKEN", "")

app = FastAPI(title="Prelude Opus Session Server", version="0.9.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def request_id_of(x_request_id: str | None) -> str:
    return x_request_id or str(uuid4())


def fail(status: int, code: str, message: str, request_id: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"error": {"code": code, "message": message, "requestId": request_id}},
    )


def authorize(authorization: str | None, x_device_id: str | None, request_id: str) -> str:
    device_id = (x_device_id or "").strip() or "unknown-device"
    expected = DEV_TOKEN.strip()
    if not expected:
        return device_id
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token != expected:
        raise fail(401, "unauthorized", "device token failed", request_id)
    return device_id


@app.get("/health")
def health() -> dict[str, object]:
    sessions = 0
    try:
        with connect() as conn:
            sessions = int(conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
    except Exception:
        pass
    return {"status": "ok", "db": str(DB_PATH), "sessions": sessions}


@app.get("/v1")
def api_index() -> dict[str, object]:
    return {
        "service": "Prelude Opus Session Server",
        "dashboard": "/",
        "health": "/health",
        "post": [
            "/v1/sessions",
            "/v1/sessions/{id}/events",
            "/v1/sessions/{id}/complete",
        ],
    }


@app.post("/v1/sessions")
async def create_session(
    request: Request,
    authorization: str | None = Header(default=None),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_content_version: str | None = Header(default=None, alias="X-Content-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
):
    rid = request_id_of(x_request_id)
    device_id = authorize(authorization, x_device_id, rid)
    try:
        body = await request.json()
    except Exception as exc:
        raise fail(400, "invalid_json", str(exc), rid) from exc
    return queries.create_session(body, device_id, x_content_version, utc_now(), rid, fail)


@app.post("/v1/sessions/{session_id}/events")
async def post_events(
    session_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_content_version: str | None = Header(default=None, alias="X-Content-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
):
    rid = request_id_of(x_request_id)
    device_id = authorize(authorization, x_device_id, rid)
    try:
        body = await request.json()
    except Exception as exc:
        raise fail(400, "invalid_json", str(exc), rid) from exc
    return queries.post_events(session_id, body, device_id, x_content_version, utc_now(), rid, fail)


@app.post("/v1/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_content_version: str | None = Header(default=None, alias="X-Content-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
):
    rid = request_id_of(x_request_id)
    device_id = authorize(authorization, x_device_id, rid)
    try:
        body = await request.json()
    except Exception as exc:
        raise fail(400, "invalid_json", str(exc), rid) from exc
    return queries.complete_session(session_id, body, device_id, x_content_version, utc_now(), rid, fail)


@app.get("/v1/sessions")
def list_sessions(
    mode: str | None = None,
    courseId: str | None = None,
    passed: bool | None = None,
    deviceId: str | None = None,
    date: str | None = None,
    limit: int = 200,
):
    return {"sessions": queries.list_sessions(mode, courseId, passed, deviceId, date, limit)}


@app.get("/v1/sessions/{session_id}")
def get_session(session_id: str):
    payload = queries.get_session(session_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    return payload


@app.get("/v1/sessions/{session_id}/events.jsonl")
def download_jsonl(session_id: str):
    return queries.download_jsonl(session_id)


@app.get("/v1/export/sessions.csv")
def export_csv(mode: str | None = None, date: str | None = None):
    return queries.export_csv(mode, date)


@app.get("/v1/stats/daily")
def daily_stats(mode: str = "experience", date: str | None = None):
    return queries.daily_stats(mode, date)


@app.get("/v1/devices")
def list_devices():
    return {"devices": queries.list_devices()}


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "error", "message": str(exc.detail), "requestId": ""}},
    )


from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    index = os.path.join(STATIC_DIR, "index.html")
    with open(index, encoding="utf-8") as handle:
        return handle.read()
