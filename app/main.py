from __future__ import annotations

import os
import base64
import hmac
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder

from . import queries
from .db import DB_PATH, connect, init_db
from .models import CompleteRequest, EventBatchRequest, SessionCreateRequest

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DEV_TOKEN = os.environ.get("DEVICE_TOKEN", "")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
MAX_REQUEST_BYTES = int(os.environ.get("MAX_REQUEST_BYTES", str(512 * 1024)))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

app = FastAPI(title="Prelude Opus Session Server", version="0.9.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
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
    if not hmac.compare_digest(token, expected):
        raise fail(401, "unauthorized", "device token failed", request_id)
    return device_id


def authorize_admin(authorization: str | None, request_id: str) -> None:
    expected = ADMIN_TOKEN.strip()
    if not expected:
        return

    supplied = ""
    if authorization:
        if authorization.lower().startswith("bearer "):
            supplied = authorization[7:].strip()
        elif authorization.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(authorization[6:].strip()).decode("utf-8")
                _username, supplied = decoded.split(":", 1)
            except (ValueError, UnicodeDecodeError):
                supplied = ""
    if not hmac.compare_digest(supplied, expected):
        exc = fail(401, "admin_unauthorized", "administrator token required", request_id)
        exc.headers = {"WWW-Authenticate": 'Basic realm="Safety Guardians Dashboard"'}
        raise exc


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"error": {"code": "payload_too_large", "message": "request body too large", "requestId": ""}},
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "invalid_content_length", "message": "invalid Content-Length", "requestId": ""}},
            )
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, object]:
    try:
        with connect() as conn:
            sessions = int(conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database_unavailable") from exc
    return {"status": "ok", "sessions": sessions}


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
def create_session(
    body: SessionCreateRequest,
    authorization: str | None = Header(default=None),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_content_version: str | None = Header(default=None, alias="X-Content-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
):
    rid = request_id_of(x_request_id)
    device_id = authorize(authorization, x_device_id, rid)
    payload = body.model_dump(exclude_none=True)
    claimed_device = payload.get("deviceId")
    if claimed_device and claimed_device != device_id:
        raise fail(403, "device_mismatch", "body deviceId does not match X-Device-Id", rid)
    return queries.create_session(payload, device_id, x_content_version, utc_now(), rid, fail)


@app.post("/v1/sessions/{session_id}/events")
def post_events(
    session_id: str,
    body: EventBatchRequest,
    authorization: str | None = Header(default=None),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_content_version: str | None = Header(default=None, alias="X-Content-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
):
    rid = request_id_of(x_request_id)
    device_id = authorize(authorization, x_device_id, rid)
    return queries.post_events(
        session_id, body.model_dump(exclude_none=True), device_id, x_content_version, utc_now(), rid, fail
    )


@app.post("/v1/sessions/{session_id}/complete")
def complete_session(
    session_id: str,
    body: CompleteRequest,
    authorization: str | None = Header(default=None),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_content_version: str | None = Header(default=None, alias="X-Content-Version"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
):
    rid = request_id_of(x_request_id)
    device_id = authorize(authorization, x_device_id, rid)
    return queries.complete_session(
        session_id, body.model_dump(exclude_none=True), device_id, x_content_version, utc_now(), rid, fail
    )


@app.get("/v1/sessions")
def list_sessions(
    mode: str | None = None,
    courseId: str | None = None,
    passed: bool | None = None,
    deviceId: str | None = None,
    date: str | None = None,
    limit: int = 200,
    authorization: str | None = Header(default=None),
):
    authorize_admin(authorization, "")
    return {"sessions": queries.list_sessions(mode, courseId, passed, deviceId, date, limit)}


@app.get("/v1/sessions/{session_id}")
def get_session(session_id: str, authorization: str | None = Header(default=None)):
    authorize_admin(authorization, "")
    payload = queries.get_session(session_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    return payload


@app.get("/v1/sessions/{session_id}/events.jsonl")
def download_jsonl(session_id: str, authorization: str | None = Header(default=None)):
    authorize_admin(authorization, "")
    return queries.download_jsonl(session_id)


@app.get("/v1/export/sessions.csv")
def export_csv(mode: str | None = None, date: str | None = None, authorization: str | None = Header(default=None)):
    authorize_admin(authorization, "")
    return queries.export_csv(mode, date)


@app.get("/v1/stats/daily")
def daily_stats(mode: str = "experience", date: str | None = None, authorization: str | None = Header(default=None)):
    authorize_admin(authorization, "")
    return queries.daily_stats(mode, date)


@app.get("/v1/devices")
def list_devices(authorization: str | None = Header(default=None)):
    authorize_admin(authorization, "")
    return {"devices": queries.list_devices()}


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "error", "message": str(exc.detail), "requestId": ""}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "request validation failed",
                "requestId": "",
                "details": jsonable_encoder(exc.errors()),
            }
        },
    )


from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def dashboard(authorization: str | None = Header(default=None)) -> str:
    authorize_admin(authorization, "")
    index = os.path.join(STATIC_DIR, "index.html")
    with open(index, encoding="utf-8") as handle:
        return handle.read()
