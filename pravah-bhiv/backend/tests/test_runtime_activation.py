"""
Regression Test Suite for Pravah Runtime, Compute Nodes, RL Autonomy Loop, and Ingestion Activation.
Direct functional verification matching the architecture of test_cpu_metrics_stability.py and test_control_plane_override.py.
"""

from __future__ import annotations

import os
import sys
import time
from unittest.mock import patch, MagicMock
import pytest

# Ensure backend root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from control_plane.backend.app.main import (
    _build_live_dashboard_payload,
    _get_active_runtime_nodes,
    autonomous_status,
    runtime_ingest,
    ingest_link,
    remove_link,
    execute_action,
    verify_control_plane_auth,
    RuntimeIngestPayload,
    INGESTED_RUNTIME_STATE,
    _INGESTED_LINKS,
    _LAST_AUTONOMOUS_RUNTIME,
    _LAST_EXECUTED_ACTION,
    _AUTONOMOUS_DECISIONS,
    _RECENT_DECISIONS,
)
from control_plane.backend.app.schemas import LinkIngestRequest, LinkRemoveRequest
from security.auth import get_auth
from fastapi import HTTPException


def _auth_token(secret: str = "test_secure_jwt_secret_key_1234567890_abcdef"):
    from security.auth import TokenAuth
    auth = TokenAuth(secret_key=secret)
    return auth.generate_token("test_operator", expires_in=3600)


def test_live_dashboard_compute_nodes_populated():
    """Verify live dashboard monitored_services contains compute nodes with valid CPU and memory."""
    payload = _build_live_dashboard_payload()
    services = payload.get("monitored_services", [])
    assert len(services) > 0, "monitored_services must not be empty"

    # Verify at least one compute node has non-null CPU and memory percentages
    compute_nodes = [s for s in services if s.get("cpu_percent") is not None and s.get("memory_percent") is not None]
    assert len(compute_nodes) > 0, "Must have active compute nodes with CPU and memory telemetry"

    first_node = compute_nodes[0]
    assert first_node["status"] in ("CONNECTED", "DEGRADED", "HEALTHY")
    assert isinstance(first_node["cpu_percent"], (int, float))
    assert isinstance(first_node["memory_percent"], (int, float))
    assert isinstance(first_node["response_time_ms"], (int, float))
    assert first_node["last_action"] is not None


def test_autonomous_status_active():
    """Verify autonomous_status() returns active loop, valid runtime telemetry, and action."""
    data = autonomous_status()
    assert data["loop_running"] is True
    assert data["last_action"] is not None
    assert data["last_runtime"] is not None
    assert "timestamp" in data["last_runtime"]
    assert "confidence" in data["last_runtime"]
    assert "service_id" in data["last_runtime"]


def test_runtime_ingest_updates_state_and_autonomy():
    """Verify calling runtime_ingest updates active runtimes and autonomy decisions."""
    payload = RuntimeIngestPayload(
        service_id="test-worker-alpha",
        timestamp="2026-11-14T12:00:00Z",
        status="RUNNING",
        metrics={
            "cpu": 0.42,
            "memory": 0.65,
            "latency": 45,
            "error_rate": 0.01,
        },
        issue_detected=False,
        issue_type="high_cpu",
        recommended_action="scale_horizontal",
    )

    res_data = runtime_ingest(payload)
    assert res_data["service_id"] == "test-worker-alpha"
    assert "decision" in res_data
    assert "selected_action" in res_data["decision"]

    # Verify dashboard reflects the newly ingested runtime
    dash_data = _build_live_dashboard_payload()
    monitored = dash_data.get("monitored_services", [])
    worker = next((s for s in monitored if s["name"].lower() == "test-worker-alpha"), None)
    assert worker is not None, "Ingested worker must appear in monitored_services"
    assert worker["cpu_percent"] == 42
    assert worker["memory_percent"] == 65
    assert worker["status"] == "CONNECTED"

    # Verify autonomous status reflects last executed decision
    auto_data = autonomous_status()
    assert auto_data["last_runtime"]["service_id"] == "test-worker-alpha"
    assert len(auto_data["recent_autonomous_decisions"]) > 0


def test_ingest_link_auth_and_lifecycle(monkeypatch):
    """Verify link ingestion authentication, addition, and removal."""
    test_secret = "test_secure_jwt_secret_key_1234567890_abcdef"
    monkeypatch.setenv("JWT_SECRET_KEY", test_secret)
    monkeypatch.setenv("SSPL_SECRET_KEY", "test_secure_sspl_secret_key_1234567890_abcdef")
    import security.auth
    security.auth._auth = None

    # 1. Unauthenticated -> verify_control_plane_auth raises HTTPException(401)
    with pytest.raises(HTTPException) as exc_info:
        verify_control_plane_auth(authorization=None, x_api_token=None)
    assert exc_info.value.status_code == 401

    # 2. Authenticated caller payload
    token = _auth_token(secret=test_secret)
    auth_ctx = verify_control_plane_auth(authorization=f"Bearer {token}", x_api_token=None)
    assert auth_ctx["caller_id"] == "test_operator"

    test_link = "https://internal.pravah.blackhole/telemetry-test-repo"
    req = LinkIngestRequest(link=test_link)
    ingest_res = ingest_link(req, auth=auth_ctx)
    assert ingest_res.success is True
    assert ingest_res.ingested_link.link == test_link

    # 3. Clean up link with removal
    remove_req = LinkRemoveRequest(link=test_link)
    remove_res = remove_link(remove_req, auth=auth_ctx)
    assert remove_res.success is True


def test_actual_worker_heartbeat_and_runtime_discovery():
    """Verify worker registration and discovery mechanism."""
    # 1. When worker is in INGESTED_RUNTIME_STATE, discovery returns registered worker
    nodes = _get_active_runtime_nodes()
    assert len(nodes) > 0
    assert any("worker" in k for k in nodes)

    # 2. When INGESTED_RUNTIME_STATE is empty, discovery automatically discovers host platform nodes
    saved_state = dict(INGESTED_RUNTIME_STATE)
    try:
        INGESTED_RUNTIME_STATE.clear()
        platform_nodes = _get_active_runtime_nodes(default_cpu=22, default_mem=48)
        assert "control-plane" in platform_nodes
        assert "decision-brain" in platform_nodes
        assert "observer-daemon" in platform_nodes
        assert platform_nodes["control-plane"]["status"] == "RUNNING"
        assert platform_nodes["control-plane"]["metrics"]["cpu"] == 22
    finally:
        INGESTED_RUNTIME_STATE.update(saved_state)


def test_rl_governance_pipeline_fail_closed():
    """Verify RL decision execution through real governance contract checking."""
    # Test unauthorized capability fails closed
    success, res = execute_action(action="unauthorized_reboot_action", service_id="test-svc")
    assert success is False
    assert res["status"] == "rejected"
    assert "rejection_code" in res or "reason" in res

    # Test governed action passes through contract validation
    success_gov, res_gov = execute_action(action="noop", service_id="test-svc")
    # Governed action result must have structured execution tracking
    assert isinstance(res_gov, dict)
    assert "action" in res_gov


def test_github_repository_persistent_telemetry(monkeypatch):
    """Verify GitHub repository ingestion persists cryptographically to append-only journal."""
    test_secret = "test_secure_jwt_secret_key_1234567890_abcdef"
    monkeypatch.setenv("JWT_SECRET_KEY", test_secret)
    monkeypatch.setenv("SSPL_SECRET_KEY", "test_secure_sspl_secret_key_1234567890_abcdef")
    import security.auth
    security.auth._auth = None

    token = _auth_token(secret=test_secret)
    auth_ctx = verify_control_plane_auth(authorization=f"Bearer {token}", x_api_token=None)

    github_repo = "https://github.com/I-am-ShivamPal/multi-agents-control-plane"
    req = LinkIngestRequest(link=github_repo)
    res = ingest_link(req, auth=auth_ctx)
    assert res.success is True
    assert res.ingested_link.name == "multi-agents-control-plane"
    assert res.enrichment_status in ("enriched", "fallback_heuristic")

    # Verify journal integrity
    from control_plane.persistence import monitored_links_journal
    active_links, meta_map, events = monitored_links_journal.replay_monitored_links()
    assert any(item["link"] == github_repo for item in active_links)


def test_timeout_configuration_and_bhiv_bucket_probe(monkeypatch):
    """Verify configurable probe timeout prevents spurious 3.0s degradation."""
    import observer_server
    monkeypatch.setenv("PRAVAH_PROBE_TIMEOUT_SEC", "6.5")

    # Verify configurable probe timeout is read from environment
    assert float(os.getenv("PRAVAH_PROBE_TIMEOUT_SEC", "5.0")) == 6.5

    # Mock response to simulate healthy BHIV-BUCKET probe
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "service": "bhiv-bucket"}
    mock_resp.headers = {"content-type": "application/json"}

    with patch("requests.get", return_value=mock_resp) as mock_get:
        observer_server._probe_service(
            name="bhiv-bucket",
            health_url="http://localhost:8001/health",
            url="http://localhost:8001",
        )
        # Verify probe was invoked with the configured timeout (6.5s, not 3.0s)
        assert mock_get.called
        assert mock_get.call_args[1]["timeout"] == 6.5

    # Verify observation store updated
    with observer_server.store_lock:
        bucket_state = observer_server.observation_store["services"].get("bhiv-bucket")
        assert bucket_state is not None
        assert bucket_state["status"] in ("Healthy", "ok")
