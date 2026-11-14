"""
Canonical Decision API Layer

Exposes only:
- POST /api/runtime
- GET  /api/status
- GET  /api/health
- GET  /api/control-plane/apps
- GET  /api/control-plane/health
- GET  /api/control-plane/history/<app_name>
- POST /api/control-plane/override
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timezone
import json
import logging
import os
import requests
import sys
import threading
import time

logger = logging.getLogger("control_plane.agent_api")
# Ensure repo root is on sys.path so running this module directly works
# agent_api.py is at control_plane/api; repo root is two levels up
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if root_dir not in sys.path:
    sys.path.append(root_dir)
from core_hooks.middleware import verify_request_trace
from jsonschema import ValidationError, validate  # type: ignore[import-untyped]
from core_hooks.rules import validate_trace



from agent_runtime import AgentRuntime
import agent_runtime
print("[RUNTIME] USING RUNTIME FILE:", agent_runtime.__file__)
from control_plane.multi_app_control_plane import MultiAppControlPlane
from control_plane.core.input_validator import InputValidator, ValidationError as InputValidationError

ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

# Resolve canonical schema path across current/legacy layouts.
schema_candidates = [
    os.path.join(root_dir, "schemas", "signal_schema.json"),
    os.path.join(os.path.dirname(root_dir), "schemas", "signal_schema.json"),
    os.path.join(os.path.dirname(root_dir), "runtime_payload_schema.json"),
]
SCHEMA_PATH = next((path for path in schema_candidates if os.path.exists(path)), schema_candidates[0])


with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
    RUNTIME_SCHEMA = json.load(schema_file)

# One shared runtime instance
agent = AgentRuntime(env=ENVIRONMENT)
control_plane = MultiAppControlPlane(env=ENVIRONMENT)


def start_agent_loop() -> None:
    """Run autonomous loop in background."""
    try:
        print("[AGENT] Starting agent loop in background...")
        agent.run()
    except Exception as e:
        print(f"[AGENT] ERROR: Agent loop crashed: {e}")


# Start agent loop in daemon background thread with delayed start
# This prevents blocking Flask initialization and process shutdown
if os.getenv("ENABLE_AGENT_LOOP", "true").lower() == "true" and "pytest" not in sys.modules and not os.getenv("PYTEST_CURRENT_TEST"):
    agent_thread = threading.Thread(target=start_agent_loop, daemon=True, name="AgentLoopThread")
    agent_thread.start()
    print("[INFO] Agent background thread started")


app = Flask(__name__)
_cors_env = os.getenv("BACKEND_CORS_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip() and o.strip() != "*"] if _cors_env else [
    "http://localhost:4500",
    "http://localhost:3200",
    "http://localhost:3000",
    "https://pravah.blackholeinfiverse.com",
]
CORS(app, resources={r"/*": {"origins": _cors_origins}})

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Application HTTP request telemetry middleware (streams non-sensitive latency and status to Observer)
try:
    from telemetry_client import setup_flask_telemetry
    setup_flask_telemetry(app, service_name="control-plane")
except Exception as _tel_exc:
    logger.warning("Could not setup Flask telemetry: %s", _tel_exc)


def _validate_runtime_payload(payload: dict) -> None:
    validate(instance=payload, schema=RUNTIME_SCHEMA)

def _event_type_from_contract(payload: dict) -> str:
    """Derive internal event type from canonical runtime contract."""
    state = payload.get("state")
    latency_ms = payload.get("latency_ms", 0)
    errors_last_min = payload.get("errors_last_min", 0)

    if state == "crashed":
        return "crash"

    if state == "degraded" or latency_ms >= 200 or errors_last_min >= 5:
        return "overload"

    return "false_alarm"


def _to_agent_event(payload: dict) -> dict:
    return {
        "trace_id": payload["trace_id"],  # [OK] ADD THIS
        "event_id": f"runtime-{datetime.now(timezone.utc).timestamp()}",
        "event_type": _event_type_from_contract(payload),
        "environment": payload["env"],
        "app_id": payload["app"],
        "timestamp": datetime.now(timezone.utc).timestamp(),
        "data": {
            "state": payload["state"],
            "metrics": {
                "latency_ms": payload["latency_ms"],
                "errors_last_min": payload["errors_last_min"],
                "workers": payload["workers"],
            },
        },
    }


@app.route("/api/health", methods=["GET"])
@limiter.limit("100 per minute")
def health_check():
    """Health and liveness endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "canonical-decision-api",
        "environment": ENVIRONMENT,
    }), 200


@app.route("/api/status", methods=["GET"])
@limiter.limit("60 per minute")
def runtime_status():
    """Return current status of the shared runtime instance."""
    try:
        status = agent.get_agent_status()
        return jsonify(status), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/runtime", methods=["POST"])
@limiter.limit("30 per minute")
def runtime_decision():
    """Canonical runtime decision endpoint."""

    payload = request.get_json(silent=True)

    if payload is None:
        return jsonify({
            "status": "error",
            "error": "Request body must be valid JSON",
        }), 400

    try:
        payload = verify_request_trace(payload)

    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": "Trace verification failed",
            "details": str(exc),
        }), 401

    # [OK] Enforce trace
    try:
        validate_trace(payload)
    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": "Trace validation failed",
            "details": str(exc),
        }), 400

    # [OK] Hardened input validation
    try:
        InputValidator.validate_runtime_payload(payload)
    except InputValidationError as exc:
        return jsonify({
            "status": "error",
            "error": "Input validation failed",
            "details": str(exc),
        }), 400
    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": "Runtime payload validation failed",
            "details": str(exc),
        }), 400

    try:
        result = agent.handle_external_event(_to_agent_event(payload))

        # Forward telemetry to observer dashboard out-of-band
        obs_port = 8600
        try:
            obs_port = int(os.getenv("PRAVAH_OBSERVER_PORT", "8600"))
            obs_host = os.getenv("PRAVAH_OBSERVER_HOST", "observer" if ENVIRONMENT == "prod" else "127.0.0.1")
            obs_url = os.getenv("PRAVAH_OBSERVER_URL", f"http://{obs_host}:{obs_port}/api/ingest")
            requests.post(
                obs_url,
                json={
                    "service": payload.get("app", "unknown"),
                    "status": payload.get("state", "info"),
                    "data": {
                        "trace_id": payload.get("trace_id"),
                        "latency_ms": payload.get("latency_ms", 0),
                        "errors_last_min": payload.get("errors_last_min", 0),
                        "decision": result
                    }
                },
                timeout=1.0
            )
        except Exception as exc:
            logger.warning("Observer event forward failed (obs_port=%s): %s", obs_port, exc)
            # Observer down should not affect the control plane execution authority

        return jsonify({
            "status": "success",
            "input": payload,
            "result": result,
        }), 200

    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": "Runtime decision failed",
            "details": str(exc),
        }), 500


@app.route("/api/control-plane/apps", methods=["GET"])
@limiter.limit("40 per minute")
def control_plane_apps():
    """List all onboarded apps in the registry."""
    try:
        return jsonify({"status": "success", "apps": control_plane.list_apps()}), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/control-plane/health", methods=["GET"])
@limiter.limit("40 per minute")
def control_plane_health_overview():
    """Health overview dashboard data for all onboarded apps."""
    try:
        return jsonify({"status": "success", "overview": control_plane.get_health_overview()}), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/control-plane/history/<app_name>", methods=["GET"])
@limiter.limit("40 per minute")
def control_plane_history(app_name: str):
    """Decision history timeline for one app."""
    try:
        # Validate app_name
        app_name = InputValidator.validate_app_name(app_name)

        # Validate limit parameter
        limit_param = request.args.get("limit", "200")
        limit = InputValidator.validate_limit_param(limit_param)

        history = control_plane.get_decision_history(app_name=app_name, limit=limit)
        return jsonify({"status": "success", "app_name": app_name, "timeline": history}), 200
    except InputValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/control-plane/override", methods=["POST"])
@limiter.limit("40 per minute")
def control_plane_override():
    """Manual override panel actions: set or clear temporary per-app freeze.

    Accepts both frontend-native field names and legacy validator names:
      action: "freeze" | "clear_freeze"   (frontend sends "freeze"; validator expects "set_freeze")
      duration: <seconds>                 (frontend sends seconds; validator expects duration_minutes)
    """
    payload = request.get_json(silent=True) or {}

    # --- Normalise frontend action aliases before validation ---
    # The frontend form sends action="freeze"; the validator requires "set_freeze".
    # Map the alias here so the governance validator is never bypassed.
    normalised = dict(payload)
    if normalised.get("action") == "freeze":
        normalised["action"] = "set_freeze"

    # The frontend sends duration in seconds (field: "duration").
    # The validator reads duration_minutes.  Convert only when duration_minutes
    # is absent, ensuring existing callers that already send duration_minutes
    # are unaffected.
    if "duration_minutes" not in normalised and "duration" in normalised:
        try:
            duration_sec = int(normalised["duration"])
            # Round up to at least 1 minute; cap at 24 h (validator enforces 1–1440).
            normalised["duration_minutes"] = max(1, duration_sec // 60)
        except (TypeError, ValueError):
            pass  # Let the validator surface a typed error.

    try:
        app_name, action, duration, reason = InputValidator.validate_control_plane_override_payload(normalised)
    except InputValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    try:
        if action == "clear_freeze":
            result = control_plane.clear_manual_override(app_name)
        else:
            result = control_plane.set_manual_override(app_name, duration, reason)
        return jsonify({"status": "success", "result": result}), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


# ── GC-Shakti Integration Endpoints ──────────────────────────────────────────

EVIDENCE_STORE_PATH = os.path.join(root_dir, "data", "evidence_bundles.json")

def check_shakti_auth():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
    token = auth_header.split(" ")[1]
    expected_token = os.getenv("PRAVAH_API_KEY")
    if not expected_token:
        if ENVIRONMENT == "prod":
            logger.error("PRAVAH_API_KEY is not set in production; rejecting auth")
            return False
        expected_token = "shakti-secret-key-change-in-prod"
    elif ENVIRONMENT == "prod" and expected_token in {"shakti-secret-key-change-in-prod", "dev-key", "change-me"}:
        logger.error("Insecure default PRAVAH_API_KEY detected in production; rejecting auth")
        return False

    # Check X-Source-System header against allowed ecosystem sources
    source_system = request.headers.get("X-Source-System")
    allowed_sources = {"SHAKTI", "BHIV_MASTERDB", "WORKFLOW_BLACKHOLE", "UNIGURU"}
    if source_system not in allowed_sources:
        return False

    return token == expected_token

def load_evidence_bundles():
    if not os.path.exists(EVIDENCE_STORE_PATH):
        os.makedirs(os.path.dirname(EVIDENCE_STORE_PATH), exist_ok=True)
        return {}
    try:
        with open(EVIDENCE_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Evidence store root must be a JSON object")
            return data
    except Exception as exc:
        logger.error("Failed to load evidence bundles from '%s': %s", EVIDENCE_STORE_PATH, exc)
        raise RuntimeError(f"Evidence store corrupted or unreadable: {exc}") from exc

def save_evidence_bundle(evidence_ref: str, bundle: dict) -> bool:
    try:
        store = load_evidence_bundles()
        store[evidence_ref] = bundle
        store_dir = os.path.dirname(EVIDENCE_STORE_PATH)
        if store_dir:
            os.makedirs(store_dir, exist_ok=True)
        temp_file = f"{EVIDENCE_STORE_PATH}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, EVIDENCE_STORE_PATH)
        return True
    except Exception as exc:
        logger.error("Failed to save evidence bundle '%s' to '%s': %s", evidence_ref, EVIDENCE_STORE_PATH, exc)
        return False

@app.route("/pravah/events", methods=["POST"])
@app.route("/pravah/api/v1/publish", methods=["POST"])
@limiter.exempt
def shakti_events():
    if not check_shakti_auth():
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"status": "error", "error": "Request body must be valid JSON"}), 400

    required_fields = ["trace_id", "correlation_id", "source", "action", "event_type", "payload", "source_system", "published_at"]
    for field in required_fields:
        if field not in payload:
            return jsonify({"status": "error", "error": f"Missing required field: {field}"}), 400

    response_payload = {
        "status": "CONNECTED",
        "detail": "Event published to Pravah pipeline",
        "trace_id": payload["trace_id"],
        "event_type": payload["event_type"],
        "pipeline_latency_ms": 12,
        "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    try:
        control_plane.append_decision_history({
            "app_name": "shakti-gc",
            "executed_action": payload["action"],
            "reason": f"Ecosystem event: {payload['event_type']}",
            "execution_success": True,
            "event": {
                "trace_id": payload["trace_id"],
                "correlation_id": payload["correlation_id"]
            }
        })
    except Exception as exc:
        logger.error("Failed to append decision history for Shakti event (trace_id=%s): %s", payload.get("trace_id"), exc)
        return jsonify({
            "status": "error",
            "error": "Audit persistence failed",
            "details": str(exc),
        }), 500

    return jsonify(response_payload), 200

@app.route("/evidence", methods=["POST"])
@limiter.exempt
def shakti_publish_evidence():
    if not check_shakti_auth():
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"status": "error", "error": "Request body must be valid JSON"}), 400

    required_fields = ["bundle_id", "trace_id", "execution_id", "decision_id", "decision_type", "authority_chain", "evidence", "produced_at", "correlation_id", "source", "action"]
    for field in required_fields:
        if field not in payload:
            return jsonify({"status": "error", "error": f"Missing required field: {field}"}), 400

    import uuid
    evidence_ref = f"ev-{uuid.uuid4().hex[:16]}"
    saved = save_evidence_bundle(evidence_ref, payload)
    if not saved:
        return jsonify({"status": "error", "error": "Evidence persistence failed"}), 500

    response_payload = {
        "evidence_ref": evidence_ref,
        "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    return jsonify(response_payload), 200

@app.route("/evidence/<evidence_ref>", methods=["GET"])
@limiter.exempt
def shakti_retrieve_evidence(evidence_ref: str):
    if not check_shakti_auth():
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    try:
        store = load_evidence_bundles()
    except Exception as exc:
        return jsonify({"status": "error", "error": f"Evidence store unavailable: {exc}"}), 500

    bundle = store.get(evidence_ref)
    if not bundle:
        return jsonify({"status": "error", "error": "Evidence bundle not found"}), 404

    return jsonify(bundle), 200

@app.route("/registry/trace/<trace_id>", methods=["GET"])
@limiter.exempt
def query_unified_registry(trace_id: str):
    if not check_shakti_auth():
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    from control_plane.core.registry_manager import RegistryManager
    manager = RegistryManager(base_dir=root_dir)
    result = manager.query_trace_lineage(trace_id)
    return jsonify(result), 200

@app.route("/metrics", methods=["GET"])
@limiter.exempt
def prometheus_metrics():
    failures = 0
    recoveries = 0
    stability_score = None
    history_parse_error = False

    # 1. Parse decision history log to count failures/recoveries
    history_file = os.path.join(root_dir, "logs", "control_plane", "decision_history.jsonl")
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    action = record.get("executed_action") or record.get("action")
                    if action in ["scale_up", "heal", "restart"]:
                        recoveries += 1
                    elif record.get("state") == "degraded" or record.get("event_type") == "crash":
                        failures += 1
            # Compute stability score only after successful read and parse
            raw_score = 100 - (failures * 2) + (recoveries * 3)
            stability_score = max(0, min(100, raw_score))
        except Exception as exc:
            logger.warning("Failed to parse decision history for metrics: %s", exc)
            history_parse_error = True
            stability_score = None
    else:
        # Default baseline when no history file has been created yet
        stability_score = 100

    # Count active apps
    from control_plane.multi_app_control_plane import MultiAppControlPlane
    cp = MultiAppControlPlane(env=ENVIRONMENT)
    try:
        apps_count = len(cp.list_apps())
    except Exception as exc:
        logger.warning("Failed to count active apps for metrics: %s", exc)
        apps_count = 0

    metrics = []
    if stability_score is not None:
        metrics.extend([
            f"# HELP pravah_stability_score Current mathematical stability score of the ecosystem",
            f"# TYPE pravah_stability_score gauge",
            f"pravah_stability_score {stability_score}",
        ])
    else:
        metrics.extend([
            f"# HELP pravah_stability_score_status Ecosystem stability score status (0=unavailable)",
            f"# TYPE pravah_stability_score_status gauge",
            f"pravah_stability_score_status{{status=\"unavailable\"}} 1",
        ])

    metrics.extend([
        f"# HELP pravah_active_apps_total Total number of registered ecosystem services",
        f"# TYPE pravah_active_apps_total gauge",
        f"pravah_active_apps_total {apps_count}",
    ])

    if not history_parse_error:
        metrics.extend([
            f"# HELP pravah_recoveries_total Total number of autonomous recovery actions executed",
            f"# TYPE pravah_recoveries_total counter",
            f"pravah_recoveries_total {recoveries}",
            f"# HELP pravah_failures_total Total number of system failures/degradations observed",
            f"# TYPE pravah_failures_total counter",
            f"pravah_failures_total {failures}",
        ])
    else:
        metrics.extend([
            f"# HELP pravah_decision_history_parse_errors_total Total number of parse failures encountered reading decision history",
            f"# TYPE pravah_decision_history_parse_errors_total counter",
            f"pravah_decision_history_parse_errors_total 1",
        ])

    return "\n".join(metrics) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4"}



@app.route("/live", methods=["GET"])
def liveness():
    """Process liveness probe (HLTH-01)."""
    return jsonify({"status": "alive", "service": "control-plane", "timestamp": datetime.now(timezone.utc).isoformat()}), 200


@app.route("/ready", methods=["GET"])
def readiness():
    """Process readiness probe (HLTH-02)."""
    return jsonify({
        "status": "ready",
        "service": "control-plane",
        "environment": ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


if __name__ == "__main__":
    port = int(os.getenv("CONTROL_PLANE_PORT", os.getenv("PORT", 7000)))
    app.run(host="0.0.0.0", port=port, debug=False)
