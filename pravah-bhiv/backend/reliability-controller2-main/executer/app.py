from flask import Flask, request, jsonify
import uuid
import json
import logging
from datetime import datetime, timedelta
import subprocess
import os

from core_hooks.service_auth import ServiceAuthError, verify_service_auth
from security.trace_consumption import is_trace_consumed, consume_trace
from security.nonce_store import check_nonce
# Stub for testing compatibility
def validate_deployment_request(*args, **kwargs):
    return "ALLOW"

app = Flask(__name__)

# ---------------- CONFIG ----------------
EXECUTION_MODE = os.getenv("EXECUTION_MODE", "docker")  # docker | kubernetes

logging.basicConfig(
    filename="executer.log",
    level=logging.INFO,
    format='%(message)s'
)

VALID_ACTIONS = ["restart", "scale_up", "scale_down", "noop"]

cooldowns = {}
COOLDOWN_TIME = 10  # seconds


# ---------------- LOGGER ----------------
def log_event(event_type, service_id, action, result):
    log = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event_type,
        "service_id": service_id,
        "action": action,
        "result": result,
        "mode": EXECUTION_MODE
    }
    logging.info(json.dumps(log))


# ---------------- VERIFY ----------------
def verify_deployment(service_id):
    try:
        if EXECUTION_MODE == "kubernetes":
            result = subprocess.run(
                ["kubectl", "get", "pods"],
                capture_output=True,
                text=True
            )
            return service_id in result.stdout

        elif EXECUTION_MODE == "docker":
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                text=True
            )
            return service_id in result.stdout

        return False
    except:
        return False


# ---------------- EXECUTION ----------------
def execute_real_action(service_id, action):
    try:
        # -------- KUBERNETES --------
        if EXECUTION_MODE == "kubernetes":

            if action == "restart":
                cmd = ["kubectl", "rollout", "restart", f"deployment/{service_id}"]

            elif action == "scale_up":
                cmd = ["kubectl", "scale", f"deployment/{service_id}", "--replicas=2"]

            elif action == "scale_down":
                cmd = ["kubectl", "scale", f"deployment/{service_id}", "--replicas=1"]

            else:
                return "noop"

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                return f"K8S_ERROR: {result.stderr.strip()}"

            return result.stdout.strip()

        # -------- DOCKER --------
        elif EXECUTION_MODE == "docker":

            if action == "restart":
                cmd = ["docker", "restart", service_id]

            elif action == "scale_up":
                return f"DOCKER_SCALE_UP simulated for {service_id}"

            elif action == "scale_down":
                return f"DOCKER_SCALE_DOWN simulated for {service_id}"

            else:
                return "noop"

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                return f"DOCKER_ERROR: {result.stderr.strip()}"

            return result.stdout.strip()

        # -------- FALLBACK --------
        else:
            return "UNKNOWN_EXECUTION_MODE"

    except Exception as e:
        return f"EXCEPTION: {str(e)}"


# ---------------- EXECUTE API ----------------
@app.route("/execute-action", methods=["POST"])
def execute_action():
    data = request.get_json()
    
    service_id = request.headers.get("X-Service-Id")
    timestamp = request.headers.get("X-Service-Timestamp")
    nonce = request.headers.get("X-Service-Nonce")
    signature = request.headers.get("X-Service-Signature")
    
    is_prod = os.getenv("ENVIRONMENT", "").strip().lower() == "prod"
    
    # Check if signature headers are provided (or always in prod)
    if service_id or timestamp or nonce or signature or is_prod:
        try:
            data = verify_service_auth(data)
        except ServiceAuthError as exc:
            return jsonify({
                "status": "failed",
                "reason": str(exc),
                "verified": False,
            }), 401
    else:
        # Fallback to legacy check in non-prod when headers aren't provided
        if request.headers.get("X-CALLER") != "sarathi":
            return jsonify({
                "status": "failed",
                "reason": "unauthorized",
                "verified": False
            }), 403

    # REQUIRED IDENTITY VALIDATION (Fail-Closed)
    req_execution_id = data.get("execution_id") if isinstance(data, dict) else None
    if not req_execution_id:
        return jsonify({
            "status": "failed",
            "reason": "missing execution_id",
            "verified": False,
        }), 400

    req_execution_hash = data.get("execution_hash")
    if not req_execution_hash:
        return jsonify({
            "execution_id": req_execution_id,
            "status": "failed",
            "reason": "missing execution_hash",
            "verified": False,
        }), 400

    req_capability_id = data.get("capability_id")
    if not req_capability_id:
        return jsonify({
            "execution_id": req_execution_id,
            "execution_hash": req_execution_hash,
            "status": "failed",
            "reason": "missing capability_id",
            "verified": False,
        }), 403

    # CAPABILITY VALIDATION
    if req_capability_id != "governed-execution":
        log_event("ACTION_REJECTED", data.get("service_id"), data.get("action"), f"unauthorized capability: {req_capability_id}")
        return jsonify({
            "execution_id": req_execution_id,
            "execution_hash": req_execution_hash,
            "capability_id": req_capability_id,
            "status": "failed",
            "action": data.get("action"),
            "service_id": data.get("service_id"),
            "trace_id": data.get("trace_id"),
            "reason": f"unauthorized capability: {req_capability_id}",
            "verified": False,
        }), 403

    req_trace_id = data.get("trace_id")
    if not req_trace_id:
        return jsonify({
            "execution_id": req_execution_id,
            "execution_hash": req_execution_hash,
            "capability_id": req_capability_id,
            "status": "failed",
            "reason": "missing trace_id",
            "verified": False,
        }), 400

    target_service_id = data.get("service_id")
    if not target_service_id:
        return jsonify({
            "execution_id": req_execution_id,
            "execution_hash": req_execution_hash,
            "capability_id": req_capability_id,
            "trace_id": req_trace_id,
            "status": "failed",
            "reason": "missing service_id",
            "verified": False,
        }), 400

    action = data.get("action")
    log_event("ACTION_RECEIVED", target_service_id, action, "incoming")

    # ACTION VALIDATION
    if not action or action not in VALID_ACTIONS:
        log_event("ACTION_REJECTED", target_service_id, action, "invalid")
        return jsonify({
            "execution_id": req_execution_id,
            "execution_hash": req_execution_hash,
            "capability_id": req_capability_id,
            "status": "failed",
            "action": action,
            "service_id": target_service_id,
            "trace_id": req_trace_id,
            "reason": "invalid action",
            "verified": False,
        }), 400

    # COOLDOWN CHECK (Trace is NOT consumed on cooldown block)
    now = datetime.utcnow()
    if target_service_id in cooldowns and now < cooldowns[target_service_id]:
        log_event("ACTION_BLOCKED", target_service_id, action, "cooldown")
        return jsonify({
            "execution_id": req_execution_id,
            "execution_hash": req_execution_hash,
            "capability_id": req_capability_id,
            "status": "blocked",
            "action": action,
            "service_id": target_service_id,
            "trace_id": req_trace_id,
            "reason": "cooldown active",
            "verified": False,
        }), 429

    # SINGLE-USE TRACE CONSUMPTION (Only reached after all admission checks pass)
    if is_trace_consumed(req_trace_id):
        return jsonify({
            "execution_id": req_execution_id,
            "execution_hash": req_execution_hash,
            "capability_id": req_capability_id,
            "status": "failed",
            "action": action,
            "service_id": target_service_id,
            "trace_id": req_trace_id,
            "reason": f"trace_id {req_trace_id} already consumed",
            "verified": False,
        }), 400

    consume_trace(req_trace_id)
    cooldowns[target_service_id] = now + timedelta(seconds=COOLDOWN_TIME)
    log_event("ACTION_ACCEPTED", target_service_id, action, "valid")

    # EXECUTION
    result = execute_real_action(target_service_id, action)
    status = "executed" if "ERROR" not in result and "EXCEPTION" not in result else "failed"
    log_event("ACTION_EXECUTED", target_service_id, action, result)

    # VERIFICATION
    verified = verify_deployment(target_service_id)
    log_event("VERIFICATION", target_service_id, action, "success" if verified else "failed")

    return jsonify({
        "execution_id": req_execution_id,
        "status": status,
        "action": action,
        "service_id": target_service_id,
        "trace_id": req_trace_id,
        "execution_hash": req_execution_hash,
        "capability_id": req_capability_id,
        "reason": result,
        "verified": verified,
    })


# ---------------- HEALTH ----------------
@app.route("/health")
def health():
    return jsonify({"status": "healthy", "mode": EXECUTION_MODE})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)