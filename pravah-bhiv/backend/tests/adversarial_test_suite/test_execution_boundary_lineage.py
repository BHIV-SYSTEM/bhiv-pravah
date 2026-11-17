"""
Adversarial and Regression Test Suite for Phase 1.9
Execution Boundary Contract & Lineage Closure Remediation

Verifies:
1. Canonical propagation of execution_contract identity fields across Pravah -> Executor HTTP boundary:
   - execution_id, execution_hash, capability_id, trace_id, service_id, action
   - Signed headers: X-Service-Id, X-Service-Timestamp, X-Service-Nonce, X-Service-Signature
2. Post-execution lineage closure:
   - SUCCESS: CREATED -> APPROVED -> EXECUTED -> COMPLETED
   - FAILURE: CREATED -> APPROVED -> FAILED
3. Security Negative Cases A through J:
   - Case A: Missing execution contract (blocked at authorization)
   - Case B: Mismatched execution_id (detected, rejected, FAILED lineage)
   - Case C: Mismatched capability_id (rejected by executor with 403, FAILED lineage)
   - Case D: Mismatched trace_id (detected, rejected, FAILED lineage)
   - Case E: Mismatched action (detected, rejected, FAILED lineage)
   - Case F: Invalid executor response (malformed non-JSON, FAILED lineage)
   - Case G: Executor HTTP failure (500 error, FAILED lineage)
   - Case H: Network connection failure (unreachable port, FAILED lineage)
   - Case I: Successful execution -> terminal COMPLETED lineage with unbroken hash chain
   - Case J: Failed execution -> terminal FAILED lineage with no false COMPLETED state
"""

from __future__ import annotations

import http.server
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from werkzeug.serving import make_server

import pytest

# Ensure backend root and executer directory are on path
backend_dir = Path(__file__).resolve().parents[2]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

executer_dir = backend_dir / "reliability-controller2-main" / "executer"
if str(executer_dir) not in sys.path:
    sys.path.insert(0, str(executer_dir))

from control_plane.core import execution_lineage as lineage_module
from control_plane.core.execution_lineage import (
    LineageJournalState,
    _read_events,
    replay_execution_lineage,
    reset_lineage_journal_state,
)
from control_plane.backend.app.main import execute_action
from contracts.execution_contract import (
    ExecutionContract,
    advance_execution_state,
    transition_contract_state,
)
from security.signing import verify_service_request
from security.lineage_verifier import LineageVerifier


def _setup_isolated_lineage(monkeypatch, tmp_path: Path) -> Path:
    """Isolate lineage journal and reset index to guarantee sterile test execution."""
    log_path = tmp_path / "execution_lineage.jsonl"
    monkeypatch.setattr(lineage_module, "get_lineage_log_path", lambda: log_path)
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX", {})
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX_LOADED", False)
    monkeypatch.setattr(lineage_module, "_LINEAGE_STATE", LineageJournalState.UNINITIALIZED)

    # Clean governance state file to prevent inter-test cooldown or repetition interference
    gov_file = tmp_path / "governance_state.json"
    from control_plane.core.action_governance import ActionGovernance
    monkeypatch.setattr(ActionGovernance, "_load_state", lambda self: None)
    monkeypatch.setattr(ActionGovernance, "_save_state", lambda self: None)
    monkeypatch.setenv("ENVIRONMENT", "dev")

    return log_path


class ControlledMockHandler(http.server.BaseHTTPRequestHandler):
    """Configurable HTTP handler simulating various executor response behaviors."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            req_data = json.loads(body.decode("utf-8"))
        except Exception:
            req_data = {}

        self.server.received_requests.append({
            "headers": dict(self.headers),
            "body": req_data,
            "raw_body": body,
        })

        cfg = self.server.config
        status_code = cfg.get("status_code", 200)
        content_type = cfg.get("content_type", "application/json")
        response_body = cfg.get("response_body")

        if response_body is None:
            resp = {
                "execution_id": req_data.get("execution_id"),
                "status": cfg.get("status", "executed"),
                "action": req_data.get("action"),
                "service_id": req_data.get("service_id"),
                "trace_id": req_data.get("trace_id"),
                "execution_hash": req_data.get("execution_hash"),
                "capability_id": req_data.get("capability_id", "governed-execution"),
                "reason": cfg.get("reason", "Action simulated successfully"),
                "verified": cfg.get("verified", True),
            }
            if "override_fields" in cfg:
                resp.update(cfg["override_fields"])
            body_bytes = json.dumps(resp).encode("utf-8")
        elif isinstance(response_body, (dict, list)):
            body_bytes = json.dumps(response_body).encode("utf-8")
        elif isinstance(response_body, str):
            body_bytes = response_body.encode("utf-8")
        else:
            body_bytes = bytes(response_body)

        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, format, *args):
        # Silence console log noise during test runs
        pass


class ControlledExecutorServer:
    """Context manager for spinning up a loopback HTTP server with controlled behavior."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.received_requests: List[Dict[str, Any]] = []
        self.server: Optional[http.server.ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.port: Optional[int] = None

    def __enter__(self) -> ControlledExecutorServer:
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ControlledMockHandler)
        self.server.config = self.config
        self.server.received_requests = self.received_requests
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.server:
            self.server.shutdown()
            self.server.server_close()


# ==============================================================================
# Security Negative Case A: Missing Execution Contract / Unmapped Capability
# ==============================================================================
def test_case_a_missing_execution_contract(monkeypatch, tmp_path):
    """Case A: When an execution contract cannot be authorized, execution is rejected fail-closed,
    no request is sent, and no execution lineage is appended."""
    log_path = _setup_isolated_lineage(monkeypatch, tmp_path)

    # Attempt an action that has no verified capability mapping
    allowed, response = execute_action("unauthorized_action_xyz", "service-a")

    assert allowed is False
    assert response["status"] == "rejected"
    assert response["rejection_code"] == "EXECUTION_NOT_PERMITTED"
    assert "not authorized for capability" in response["reason"]

    # Verify no lineage events were written
    assert not log_path.exists() or len(_read_events()) == 0


# ==============================================================================
# Security Negative Case B: Mismatched execution_id
# ==============================================================================
def test_case_b_mismatched_execution_id(monkeypatch, tmp_path):
    """Case B: If the executor response contains an execution_id different from the contract,
    Pravah detects identity mismatch, rejects execution, and records terminal FAILED lineage."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    config = {
        "status": "executed",
        "override_fields": {"execution_id": "rogue-forged-execution-id-999"},
    }
    with ControlledExecutorServer(config) as server:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{server.port}/execute-action")

        allowed, response = execute_action("restart", "service-b")

        assert allowed is False
        assert response["status"] == "failed"
        assert response["rejection_code"] == "RESPONSE_IDENTITY_MISMATCH"
        assert "Mismatched execution_id" in response["reason"]

        # Lineage assertion: Contract must transition to FAILED, not COMPLETED
        exec_id = response["execution_id"]
        replay = replay_execution_lineage(exec_id)
        assert replay["valid"] is True
        assert replay["final_state"] == "FAILED"
        assert replay["final_state"] != "COMPLETED"
        assert replay["execution_state_history"] == ["CREATED", "APPROVED", "FAILED"]


# ==============================================================================
# Security Negative Case C: Mismatched capability_id
# ==============================================================================
def test_case_c_mismatched_capability_id(monkeypatch, tmp_path):
    """Case C: Verify that the executor rejects unauthorized capabilities with HTTP 403,
    and Pravah records terminal FAILED lineage."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    # Test executor app rejection directly:
    from app import app as executer_flask_app
    with executer_flask_app.test_client() as client:
        # Request with an unauthorized capability_id
        unauth_payload = {
            "action": "restart",
            "service_id": "service-c",
            "capability_id": "rogue-unauthorized-capability",
            "execution_id": "exec-test-c",
            "execution_hash": "hash-test-c",
            "trace_id": "trace-test-c",
        }
        from security.internal_requests import build_signed_headers
        headers = build_signed_headers("service-c", unauth_payload)
        resp = client.post("/execute-action", json=unauth_payload, headers=headers)
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["status"] == "failed"
        assert "unauthorized capability" in data["reason"]

    # Now verify Pravah handles the 403 response correctly:
    config = {
        "status_code": 403,
        "status": "failed",
        "reason": "unauthorized capability: rogue-unauthorized-capability",
    }
    with ControlledExecutorServer(config) as server:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{server.port}/execute-action")

        allowed, response = execute_action("restart", "service-c")

        assert allowed is False
        assert response["status"] == "failed"
        assert response["rejection_code"] == "EXECUTOR_EXECUTION_FAILED"

        replay = replay_execution_lineage(response["execution_id"])
        assert replay["valid"] is True
        assert replay["final_state"] == "FAILED"
        assert "COMPLETED" not in replay["execution_state_history"]


# ==============================================================================
# Security Negative Case D: Mismatched trace_id
# ==============================================================================
def test_case_d_mismatched_trace_id(monkeypatch, tmp_path):
    """Case D: If the executor returns a different trace_id than sent, Pravah detects identity
    mismatch, transitions to FAILED lineage, and returns failure."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    config = {
        "status": "executed",
        "override_fields": {"trace_id": "forged-rogue-trace-id-12345"},
    }
    with ControlledExecutorServer(config) as server:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{server.port}/execute-action")

        allowed, response = execute_action("restart", "service-d")

        assert allowed is False
        assert response["status"] == "failed"
        assert response["rejection_code"] == "RESPONSE_IDENTITY_MISMATCH"
        assert "Mismatched trace_id" in response["reason"]

        replay = replay_execution_lineage(response["execution_id"])
        assert replay["valid"] is True
        assert replay["final_state"] == "FAILED"
        assert replay["final_state"] != "COMPLETED"


# ==============================================================================
# Security Negative Case E: Mismatched action
# ==============================================================================
def test_case_e_mismatched_action(monkeypatch, tmp_path):
    """Case E: If the executor returns a different action than authorized and sent, Pravah detects
    divergence, transitions to FAILED lineage, and returns failure."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    config = {
        "status": "executed",
        "override_fields": {"action": "scale_down"},  # Sent restart, returned scale_down
    }
    with ControlledExecutorServer(config) as server:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{server.port}/execute-action")

        allowed, response = execute_action("restart", "service-e")

        assert allowed is False
        assert response["status"] == "failed"
        assert response["rejection_code"] == "RESPONSE_IDENTITY_MISMATCH"
        assert "Mismatched action" in response["reason"]

        replay = replay_execution_lineage(response["execution_id"])
        assert replay["valid"] is True
        assert replay["final_state"] == "FAILED"
        assert replay["final_state"] != "COMPLETED"


# ==============================================================================
# Security Negative Case F: Invalid / Malformed Executor Response
# ==============================================================================
def test_case_f_invalid_executor_response(monkeypatch, tmp_path):
    """Case F: If the executor returns non-JSON or malformed payload, Pravah fails closed,
    transitions contract to FAILED with MALFORMED_EXECUTOR_RESPONSE, and rejects execution."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    config = {
        "status_code": 200,
        "content_type": "text/html",
        "response_body": "<html><body>502 Bad Gateway - Upstream timeout</body></html>",
    }
    with ControlledExecutorServer(config) as server:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{server.port}/execute-action")

        allowed, response = execute_action("restart", "service-f")

        assert allowed is False
        assert response["status"] == "failed"
        assert response["rejection_code"] == "MALFORMED_EXECUTOR_RESPONSE"

        replay = replay_execution_lineage(response["execution_id"])
        assert replay["valid"] is True
        assert replay["final_state"] == "FAILED"
        assert replay["final_state"] != "COMPLETED"


# ==============================================================================
# Security Negative Case G: Executor HTTP Failure (500 Error)
# ==============================================================================
def test_case_g_executor_http_failure(monkeypatch, tmp_path):
    """Case G: When the executor returns an HTTP 500 server error, Pravah records terminal FAILED
    lineage and returns failure."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    config = {
        "status_code": 500,
        "response_body": {"status": "failed", "reason": "Internal container runtime crash"},
    }
    with ControlledExecutorServer(config) as server:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{server.port}/execute-action")

        allowed, response = execute_action("restart", "service-g")

        assert allowed is False
        assert response["status"] == "failed"
        assert response["rejection_code"] == "EXECUTOR_EXECUTION_FAILED"

        replay = replay_execution_lineage(response["execution_id"])
        assert replay["valid"] is True
        assert replay["final_state"] == "FAILED"
        assert replay["final_state"] != "COMPLETED"


# ==============================================================================
# Security Negative Case H: Network Connection Failure (Unreachable Host)
# ==============================================================================
def test_case_h_network_connection_failure(monkeypatch, tmp_path):
    """Case H: When the executor cannot be reached across the network, Pravah explicitly
    distinguishes network unreachability from rejection, records FAILED lineage with
    rejection_code EXECUTOR_UNREACHABLE, and returns failure."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    # Point to a closed port on loopback
    monkeypatch.setenv("EXECUTOR_URL", "http://127.0.0.1:1/execute-action")

    allowed, response = execute_action("restart", "service-h")

    assert allowed is False
    assert response["status"] == "failed"
    assert response["rejection_code"] == "EXECUTOR_UNREACHABLE"
    assert "Network failure contacting executor" in response["reason"]

    replay = replay_execution_lineage(response["execution_id"])
    assert replay["valid"] is True
    assert replay["final_state"] == "FAILED"
    assert replay["final_state"] != "COMPLETED"
    assert replay["execution_state_history"] == ["CREATED", "APPROVED", "FAILED"]


# ==============================================================================
# Test I: Successful Execution -> Correct Full Lineage Closure
# ==============================================================================
def test_case_i_successful_execution_terminal_lineage(monkeypatch, tmp_path):
    """Case I: Upon successful execution, verify:
    1. Canonical execution contract fields (execution_id, execution_hash, capability_id, trace_id,
       service_id, action) are received across the boundary and HMAC-verified.
    2. Post-execution lineage closes with full legal FSM path:
       CREATED -> APPROVED -> EXECUTED -> COMPLETED
    3. Replay verification passes: valid=True, final_state=COMPLETED, unbroken hash chaining.
    """
    _setup_isolated_lineage(monkeypatch, tmp_path)

    config = {
        "status": "executed",
        "reason": "Container restarted successfully",
        "verified": True,
    }
    with ControlledExecutorServer(config) as server:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{server.port}/execute-action")

        allowed, response = execute_action("restart", "service-i")

        assert allowed is True
        assert response["status"] == "executed"

        # Verify the request received by the executor
        assert len(server.received_requests) == 1
        received = server.received_requests[0]
        req_headers = received["headers"]
        req_body = received["body"]

        # Check authenticated transport fields
        assert req_body["action"] == "restart"
        assert req_body["service_id"] == "service-i"
        assert "execution_id" in req_body and req_body["execution_id"]
        assert "execution_hash" in req_body and len(req_body["execution_hash"]) == 64
        assert req_body["capability_id"] == "governed-execution"
        assert "trace_id" in req_body and req_body["trace_id"].startswith("trace-")

        # Cryptographically verify the request headers using production verifier
        is_valid_hmac = verify_service_request(
            service_id=req_headers["X-Service-Id"],
            timestamp=req_headers["X-Service-Timestamp"],
            nonce=req_headers["X-Service-Nonce"],
            signature=req_headers["X-Service-Signature"],
            payload_dict=req_body,
        )
        assert is_valid_hmac is True

        # Assert full lineage closure
        exec_id = req_body["execution_id"]
        replay = replay_execution_lineage(exec_id)

        assert replay["valid"] is True
        assert replay["final_state"] == "COMPLETED"
        assert replay["execution_state_history"] == ["CREATED", "APPROVED", "EXECUTED", "COMPLETED"]

        # Verify hash chain continuity
        events = replay["events"]
        assert len(events) == 4
        assert events[0]["state"] == "CREATED"
        assert events[1]["state"] == "APPROVED"
        assert events[2]["state"] == "EXECUTED"
        assert events[3]["state"] == "COMPLETED"

        assert events[0]["parent_hash"] == ""
        assert events[1]["parent_hash"] == events[0]["trace_hash"]
        assert events[2]["parent_hash"] == events[1]["trace_hash"]
        assert events[3]["parent_hash"] == events[2]["trace_hash"]


# ==============================================================================
# Test J: Failed Execution -> No False COMPLETED Lineage
# ==============================================================================
def test_case_j_failed_execution_no_completed_lineage(monkeypatch, tmp_path):
    """Case J: When the executor returns a failed execution status (e.g. HTTP 200 with
    status="failed"), Pravah does not mark execution completed, records FAILED lineage,
    and replay verification proves final_state is FAILED and COMPLETED was never recorded."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    config = {
        "status_code": 200,
        "status": "failed",
        "reason": "Docker error: container failed to restart",
        "verified": False,
    }
    with ControlledExecutorServer(config) as server:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{server.port}/execute-action")

        allowed, response = execute_action("restart", "service-j")

        assert allowed is False
        assert response["status"] == "failed"
        assert response["rejection_code"] == "EXECUTOR_EXECUTION_FAILED"

        exec_id = response["execution_id"]
        replay = replay_execution_lineage(exec_id)

        assert replay["valid"] is True
        assert replay["final_state"] == "FAILED"
        assert replay["final_state"] != "COMPLETED"
        assert "COMPLETED" not in replay["execution_state_history"]
        assert replay["execution_state_history"] == ["CREATED", "APPROVED", "FAILED"]


# ==============================================================================
# Integration Test: Real Executor Flask Application Loopback Validation
# ==============================================================================
def test_real_executor_flask_app_boundary(monkeypatch, tmp_path):
    """Integration test running the actual production executer/app.py Flask application
    over a real loopback WSGI server, proving real HMAC verification, trace consumption,
    execution_id preservation, and lineage closure without any mocks on security controls."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    from app import app as real_executer_flask_app
    server = make_server("127.0.0.1", 0, real_executer_flask_app)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{port}/execute-action")

        # Because Docker is not running in test env, the real executer will return
        # status="failed" with DOCKER_ERROR or EXCEPTION.
        # This exercises the REAL execution path, REAL HMAC verification in executer/app.py,
        # REAL trace consumption, and Pravah's fail-closed handling!
        allowed, response = execute_action("restart", "service-real")

        assert allowed is False
        assert response["status"] == "failed"
        assert response["rejection_code"] == "EXECUTOR_EXECUTION_FAILED"

        # Check that execution_id was preserved and not overwritten
        exec_id = response["execution_id"]
        assert exec_id == response["response"]["execution_id"]

        # Check lineage
        replay = replay_execution_lineage(exec_id)
        assert replay["valid"] is True
        assert replay["final_state"] == "FAILED"
        assert "COMPLETED" not in replay["execution_state_history"]
    finally:
        server.shutdown()
        server.server_close()


# ==============================================================================
# Phase 1.9.2 Hardening Regressions: G1, G2, G3, G4, G5, G6, G7
# ==============================================================================

def test_executor_missing_execution_id_rejected(tmp_path):
    """G2: Executor must reject missing execution_id with HTTP 400 and not invent a UUID."""
    from app import app as executer_flask_app
    from security.internal_requests import build_signed_headers
    with executer_flask_app.test_client() as client:
        payload = {
            "action": "restart",
            "service_id": "service-g2",
            "capability_id": "governed-execution",
            "execution_hash": "hash-g2",
            "trace_id": "trace-g2",
        }
        headers = build_signed_headers("service-g2", payload)
        resp = client.post("/execute-action", json=payload, headers=headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["status"] == "failed"
        assert "missing execution_id" in data["reason"]


def test_executor_missing_capability_id_rejected(tmp_path):
    """G1: Executor must reject missing capability_id with HTTP 403 fail-closed."""
    from app import app as executer_flask_app
    from security.internal_requests import build_signed_headers
    with executer_flask_app.test_client() as client:
        payload = {
            "execution_id": "exec-g1-missing",
            "action": "restart",
            "service_id": "service-g1",
            "execution_hash": "hash-g1",
            "trace_id": "trace-g1",
        }
        headers = build_signed_headers("service-g1", payload)
        resp = client.post("/execute-action", json=payload, headers=headers)
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["status"] == "failed"
        assert "missing capability_id" in data["reason"]


def test_executor_missing_execution_hash_rejected(tmp_path):
    """G4: Executor must reject missing execution_hash with HTTP 400."""
    from app import app as executer_flask_app
    from security.internal_requests import build_signed_headers
    with executer_flask_app.test_client() as client:
        payload = {
            "execution_id": "exec-g4-missing-hash",
            "action": "restart",
            "service_id": "service-g4",
            "capability_id": "governed-execution",
            "trace_id": "trace-g4",
        }
        headers = build_signed_headers("service-g4", payload)
        resp = client.post("/execute-action", json=payload, headers=headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["status"] == "failed"
        assert "missing execution_hash" in data["reason"]


def test_executor_missing_trace_id_rejected(tmp_path):
    """G3/Boundary: Executor must reject missing trace_id with HTTP 400."""
    from app import app as executer_flask_app
    from security.internal_requests import build_signed_headers
    with executer_flask_app.test_client() as client:
        payload = {
            "execution_id": "exec-missing-trace",
            "action": "restart",
            "service_id": "service-trace",
            "capability_id": "governed-execution",
            "execution_hash": "hash-trace",
        }
        headers = build_signed_headers("service-trace", payload)
        resp = client.post("/execute-action", json=payload, headers=headers)
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["status"] == "failed"
        assert "missing trace_id" in data["reason"]


def test_response_mismatched_execution_hash_rejected(monkeypatch, tmp_path):
    """G4: Pravah detects mismatched execution_hash in executor response, rejects execution,
    and records terminal FAILED lineage."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    config = {
        "status": "executed",
        "override_fields": {"execution_hash": "forged-hash-00000000000000000000000000000000"},
    }
    with ControlledExecutorServer(config) as server:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{server.port}/execute-action")

        allowed, response = execute_action("restart", "service-hash-mismatch")

        assert allowed is False
        assert response["status"] == "failed"
        assert response["rejection_code"] == "RESPONSE_IDENTITY_MISMATCH"
        assert "Mismatched execution_hash" in response["reason"]

        replay = replay_execution_lineage(response["execution_id"])
        assert replay["valid"] is True
        assert replay["final_state"] == "FAILED"
        assert replay["final_state"] != "COMPLETED"


def test_response_missing_identity_field_rejected(monkeypatch, tmp_path):
    """G5: Pravah rejects executor response missing any required identity field (e.g. capability_id)."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    # Build response body missing capability_id
    response_missing_cap = {
        "status": "executed",
        "execution_id": "exec-missing-cap-resp",
        "action": "restart",
        "service_id": "service-missing-cap",
        "trace_id": "trace-missing-cap-resp",
        "execution_hash": "dummy-hash",
        # "capability_id" intentionally omitted
    }
    config = {
        "status_code": 200,
        "response_body": response_missing_cap,
    }
    with ControlledExecutorServer(config) as server:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{server.port}/execute-action")

        allowed, response = execute_action("restart", "service-missing-cap")

        assert allowed is False
        assert response["status"] == "failed"
        assert response["rejection_code"] == "RESPONSE_IDENTITY_MISMATCH"
        assert "Missing required response identity field: capability_id" in response["reason"]

        replay = replay_execution_lineage(response["execution_id"])
        assert replay["valid"] is True
        assert replay["final_state"] == "FAILED"


def test_exception_after_approved_transitions_to_failed(monkeypatch, tmp_path):
    """G6: Unexpected exception after APPROVED transitions contract to FAILED lineage,
    preventing stranded APPROVED state."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    import requests
    def crash_post(*args, **kwargs):
        raise RuntimeError("Unexpected internal crash post-approval")
    monkeypatch.setattr(requests, "post", crash_post)

    allowed, response = execute_action("restart", "service-g6-crash")

    assert allowed is False
    assert response["status"] == "failed"
    assert response["rejection_code"] in ("EXECUTOR_UNREACHABLE", "EXECUTION_EXCEPTION")

    exec_id = response["execution_id"]
    replay = replay_execution_lineage(exec_id)
    assert replay["valid"] is True
    assert replay["final_state"] == "FAILED"
    assert replay["final_state"] != "COMPLETED"
    assert replay["execution_state_history"] == ["CREATED", "APPROVED", "FAILED"]


def test_failure_during_completion_transitions_to_failed(monkeypatch, tmp_path):
    """G7: If transition to COMPLETED fails after EXECUTED, contract transitions from
    EXECUTED -> FAILED with COMPLETION_FAILED, preventing stranded EXECUTED state."""
    _setup_isolated_lineage(monkeypatch, tmp_path)

    import contracts.execution_contract as contract_module
    orig_transition = contract_module.transition_contract_state

    def fail_on_completed(contract, state, **kwargs):
        if state == "COMPLETED":
            raise RuntimeError("Simulated completion persistence failure")
        return orig_transition(contract, state, **kwargs)

    monkeypatch.setattr(contract_module, "transition_contract_state", fail_on_completed)

    config = {
        "status": "executed",
        "reason": "Execution successful",
        "verified": True,
    }
    with ControlledExecutorServer(config) as server:
        monkeypatch.setenv("EXECUTOR_URL", f"http://127.0.0.1:{server.port}/execute-action")

        allowed, response = execute_action("restart", "service-g7-fail")

        assert allowed is False
        assert response["status"] == "failed"
        assert response["rejection_code"] == "COMPLETION_FAILED"

        exec_id = response["execution_id"]
        replay = replay_execution_lineage(exec_id)
        assert replay["valid"] is True
        assert replay["final_state"] == "FAILED"
        assert replay["final_state"] != "COMPLETED"
        assert replay["execution_state_history"] == ["CREATED", "APPROVED", "EXECUTED", "FAILED"]


def test_trace_not_consumed_on_early_rejection(tmp_path):
    """G3: Single-use trace is NOT consumed if request fails admission, capability, or action validation."""
    from app import app as executer_flask_app
    from security.trace_consumption import is_trace_consumed
    from security.internal_requests import build_signed_headers

    test_trace_id = f"trace-early-reject-{tmp_path.name}"

    with executer_flask_app.test_client() as client:
        # Step 1: Send request with INVALID action
        bad_action_payload = {
            "execution_id": "exec-early-reject",
            "action": "invalid_bad_action",
            "service_id": "service-g3",
            "capability_id": "governed-execution",
            "execution_hash": "hash-g3",
            "trace_id": test_trace_id,
        }
        headers = build_signed_headers("service-g3", bad_action_payload)
        resp = client.post("/execute-action", json=bad_action_payload, headers=headers)
        assert resp.status_code == 400
        assert "invalid action" in resp.get_json()["reason"]

        # Assert trace_id was NOT consumed!
        assert is_trace_consumed(test_trace_id) is False

        # Step 2: Send request with UNAUTHORIZED capability
        bad_cap_payload = {
            "execution_id": "exec-early-reject",
            "action": "restart",
            "service_id": "service-g3",
            "capability_id": "unauthorized-cap-xyz",
            "execution_hash": "hash-g3",
            "trace_id": test_trace_id,
        }
        headers2 = build_signed_headers("service-g3", bad_cap_payload)
        resp2 = client.post("/execute-action", json=bad_cap_payload, headers=headers2)
        assert resp2.status_code == 403
        assert "unauthorized capability" in resp2.get_json()["reason"]

        # Assert trace_id is STILL NOT consumed!
        assert is_trace_consumed(test_trace_id) is False

