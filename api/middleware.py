"""
Middleware: Rate limiter + Structured JSON audit logger + HTTP Basic Auth

Rate limiter  — in-memory, per-IP, sliding 60-second window (Apigee equivalent).
Audit logger  — one JSON line per request to logs/wms_audit.jsonl (Apigee analytics equivalent).
Basic Auth    — validates X-Supervisor-Id header or HTTP Basic credentials (Okta stub).
"""

import json
import logging
import os
import time
from collections import defaultdict
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# ---------------------------------------------------------------------------
# Audit logger (writes structured JSON to logs/wms_audit.jsonl)
# ---------------------------------------------------------------------------
_log_dir = Path("logs")
_log_dir.mkdir(exist_ok=True)

_audit_log = logging.getLogger("wms.api.audit")
_audit_log.setLevel(logging.INFO)
_handler = RotatingFileHandler(
    _log_dir / "wms_audit.jsonl",
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
)
_handler.setFormatter(logging.Formatter("%(message)s"))
_audit_log.addHandler(_handler)


def _write_audit(record: dict) -> None:
    _audit_log.info(json.dumps(record, default=str))


# ---------------------------------------------------------------------------
# In-memory rate limiter (sliding window, per client IP)
# ---------------------------------------------------------------------------
RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "60"))   # requests per window
RATE_WINDOW = int(os.getenv("API_RATE_WINDOW", "60"))  # seconds

_request_log: dict[str, list[float]] = defaultdict(list)


def _is_rate_limited(client_ip: str) -> bool:
    now = time.time()
    window_start = now - RATE_WINDOW
    timestamps = _request_log[client_ip]
    # Drop timestamps outside the sliding window
    _request_log[client_ip] = [t for t in timestamps if t > window_start]
    if len(_request_log[client_ip]) >= RATE_LIMIT:
        return True
    _request_log[client_ip].append(now)
    return False


# ---------------------------------------------------------------------------
# Auth helper (HTTP Basic or X-Supervisor-Id header — Okta stub)
# ---------------------------------------------------------------------------
API_USER = os.getenv("API_USER", "supervisor")
API_PASS = os.getenv("API_PASS", "warehouse")


def _get_supervisor(request: Request) -> str | None:
    """
    Returns the authenticated supervisor identifier, or None if anonymous.
    Priority: HTTP Basic Auth > X-Supervisor-Id header > anonymous.
    In production this would validate against Okta/SAML tokens.
    """
    # HTTP Basic Auth
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        import base64
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            user, password = decoded.split(":", 1)
            if user == API_USER and password == API_PASS:
                return user
            return None  # bad credentials → reject
        except Exception:
            return None

    # Lightweight header-based identity (no password check — for local dev)
    supervisor_id = request.headers.get("X-Supervisor-Id")
    if supervisor_id:
        return supervisor_id.strip()

    # Anonymous access allowed for local POC (remove in production)
    return "anonymous"


# ---------------------------------------------------------------------------
# Middleware class
# ---------------------------------------------------------------------------
class WMSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Skip middleware for health check and docs
        if path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        # --- Auth check ---
        supervisor = _get_supervisor(request)
        if supervisor is None:
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized", "message": "Invalid credentials."},
                headers={"WWW-Authenticate": "Basic realm=\"WMS API\""},
            )

        # --- Rate limit check ---
        if _is_rate_limited(client_ip):
            _write_audit({
                "event": "rate_limited",
                "client_ip": client_ip,
                "supervisor": supervisor,
                "path": path,
                "ts": time.time(),
            })
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit: {RATE_LIMIT} requests per {RATE_WINDOW}s.",
                },
            )

        # --- Forward to route handler ---
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        # --- Structured audit log ---
        _write_audit({
            "event": "api_request",
            "ts": time.time(),
            "supervisor": supervisor,
            "client_ip": client_ip,
            "method": request.method,
            "path": path,
            "query": str(request.query_params),
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        })

        # Add response headers for transparency
        response.headers["X-Supervisor-Id"] = supervisor
        response.headers["X-Duration-Ms"] = str(duration_ms)
        return response


def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(WMSMiddleware)
