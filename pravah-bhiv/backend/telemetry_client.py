"""
PRAVAH Application Request Telemetry Client & Middleware

Instruments FastAPI and Flask services to capture non-sensitive HTTP request metadata
and stream telemetry events out-of-band to the Observer (/api/ingest).

STRICT PRIVACY GUARDS:
- Never captures Authorization headers, cookies, passwords, or tokens.
- Never captures request bodies or sensitive query parameters.
- Normalizes paths (strips query strings and path IDs) to prevent high-cardinality leakage.
"""

from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, Optional
import urllib.parse
import urllib.request

logger = logging.getLogger("pravah.telemetry_client")

# Shared daemon thread pool for fire-and-forget telemetry emission
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pravah-telemetry")

# Regex patterns for path normalization
_UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_HEX_PATTERN = re.compile(r"^[0-9a-f]{16,}$", re.I)
_NUM_PATTERN = re.compile(r"^\d+$")


def normalize_path(path: str) -> str:
    """
    Normalizes a URL path to prevent cardinality explosion and strip sensitive IDs.
    Examples:
      /api/control-plane/history/app_123 -> /api/control-plane/history/:app
      /api/events?token=secret          -> /api/events
      /api/users/550e8400-e29b-41d4...   -> /api/users/:uuid
    """
    if not path:
        return "/"

    # Strip query string and fragment
    parsed = urllib.parse.urlparse(path)
    clean_path = parsed.path.strip()

    if not clean_path.startswith("/"):
        clean_path = "/" + clean_path

    # Normalize segments
    segments = clean_path.split("/")
    normalized = []
    for seg in segments:
        if not seg:
            continue
        if _UUID_PATTERN.match(seg):
            normalized.append(":uuid")
        elif _HEX_PATTERN.match(seg):
            normalized.append(":hash")
        elif _NUM_PATTERN.match(seg):
            normalized.append(":id")
        else:
            normalized.append(seg)

    return "/" + "/".join(normalized) if normalized else "/"


def get_observer_ingest_url() -> str:
    """Resolves the Observer /api/ingest URL across local and containerized environments."""
    custom_url = os.getenv("PRAVAH_OBSERVER_URL")
    if custom_url and custom_url.strip():
        url = custom_url.strip()
        if not url.endswith("/api/ingest"):
            url = url.rstrip("/") + "/api/ingest"
        return url

    obs_host = os.getenv("PRAVAH_OBSERVER_HOST")
    obs_port = os.getenv("PRAVAH_OBSERVER_PORT", "8600")

    if obs_host:
        return f"http://{obs_host}:{obs_port}/api/ingest"

    # Auto-detect container vs host runtime
    is_container = (os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER") == "true") and os.name != "nt"
    default_host = "observer" if is_container else "127.0.0.1"
    return f"http://{default_host}:{obs_port}/api/ingest"


def _send_telemetry_http(payload: Dict[str, Any], url: str) -> None:
    """Internal HTTP dispatcher executed in background thread."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Pravah-Application-Telemetry/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            pass
    except Exception as exc:
        # Telemetry failures MUST NEVER crash or block application request processing
        logger.debug("Non-blocking telemetry emission dropped (url=%s): %s", url, exc)


def emit_application_telemetry(
    service: str,
    method: str,
    endpoint: str,
    http_status: int,
    duration_ms: float,
    source: str = "application",
    timestamp: Optional[float] = None,
) -> None:
    """
    Submits an application request telemetry event to the background dispatcher.
    Strictly excludes sensitive payload or authorization headers.
    """
    if (
        os.getenv("PRAVAH_TELEMETRY_ENABLED", "true").lower() in ("false", "0", "off")
        or "PYTEST_CURRENT_TEST" in os.environ
    ):
        return

    normalized = normalize_path(endpoint)
    ts = timestamp if timestamp is not None else time.time()

    payload = {
        "source": source,
        "service": service,
        "method": method.upper(),
        "endpoint": normalized,
        "http_status": int(http_status),
        "latency_ms": max(0.0, float(duration_ms)),
        "timestamp": ts,
        "status": "ok" if http_status < 400 else ("degraded" if http_status < 500 else "error"),
    }

    url = get_observer_ingest_url()
    try:
        _EXECUTOR.submit(_send_telemetry_http, payload, url)
    except Exception as e:
        logger.debug("Failed to queue telemetry event: %s", e)


# =============================================================================
# FastAPI Middleware
# =============================================================================

class FastAPITelemetryMiddleware:
    """
    ASGI middleware for FastAPI services (Decision Brain).
    Measures request duration and emits telemetry to Observer.
    """

    def __init__(self, app: Any, service_name: str = "decision-brain"):
        self.app = app
        self.service_name = service_name

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "/")

        # Check for probe header
        headers = dict(scope.get("headers", []))
        is_probe = headers.get(b"x-pravah-source") == b"probe" or b"pravah-observer-probe" in headers.get(b"user-agent", b"").lower()
        source = "probe" if is_probe else "application"

        start_time = time.time()
        status_code = [200]  # mutable container to capture in send

        async def send_wrapper(message: Dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status_code[0] = message.get("status", 200)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.time() - start_time) * 1000.0
            emit_application_telemetry(
                service=self.service_name,
                method=method,
                endpoint=path,
                http_status=status_code[0],
                duration_ms=duration_ms,
                source=source,
            )


# =============================================================================
# Flask Middleware Setup Helper
# =============================================================================

def setup_flask_telemetry(app: Any, service_name: str = "control-plane") -> None:
    """
    Attaches before_request and after_request hooks to a Flask application.
    """
    from flask import g, request

    @app.before_request
    def _record_pravah_telemetry_start():
        g._pravah_telemetry_start = time.time()

    @app.after_request
    def _emit_pravah_telemetry_after(response):
        start = getattr(g, "_pravah_telemetry_start", None)
        duration_ms = ((time.time() - start) * 1000.0) if start else 0.0

        is_probe = (
            request.headers.get("X-Pravah-Source") == "probe"
            or "pravah-observer-probe" in request.headers.get("User-Agent", "").lower()
        )
        source = "probe" if is_probe else "application"

        emit_application_telemetry(
            service=service_name,
            method=request.method,
            endpoint=request.path,
            http_status=response.status_code,
            duration_ms=duration_ms,
            source=source,
        )
        return response
