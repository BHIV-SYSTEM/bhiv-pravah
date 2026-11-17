"""Tests for Phase 2.5.2 Error Boundary & Fail-Closed Security Remediation.

Validates:
1. Semantic Guard fail-closed import behavior (RuntimeError, no state mutation, no lineage event).
2. Policy Snapshot explicit validation and cryptographic binding.
3. Trace Consumption fail-closed persistence, full pre-operation rollback, and caller rejection.
4. Nonce Store fail-closed persistence, full pre-operation rollback, and caller rejection.
5. Live Dashboard & Aggregate Telemetry fail-closed & non-fabrication.
6. Shakti Event audit trail persistence failure handling with real I/O failure.
7. Observer forwarding fault tolerance and observability.
8. Evidence Bundle persistence failure and corrupt store handling with real I/O failure.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

# Ensure PRAVAH_MAIN_API is defined for AgentRuntime initialization
os.environ.setdefault("PRAVAH_MAIN_API", "http://localhost:8000")

# Ensure executer path is on sys.path
backend_dir = Path(__file__).resolve().parents[1]
executer_dir = backend_dir / "reliability-controller2-main" / "executer"
if str(executer_dir) not in sys.path:
    sys.path.append(str(executer_dir))

# Prevent Redis connection retries during test suite execution
from unittest.mock import patch, MagicMock
from control_plane.core.redis_event_bus import RedisEventBus
patch.object(RedisEventBus, "_connect", lambda self: self._setup_mock_mode()).start()

import pytest

# -----------------------------------------------------------------------------
# 1. SEMANTIC GUARD — FAIL CLOSED
# -----------------------------------------------------------------------------
from contracts.decision_contract import DecisionContract
from contracts.execution_contract import (
    ExecutionContract,
    build_execution_contract,
    advance_execution_state,
    compute_execution_hash,
)
from contracts.policy_snapshot import PolicySnapshot


def _create_sample_contract(policy_snapshot=None):
    decision = DecisionContract(
        decision_id="dec-test-1",
        decision_type="execution",
        action="scale_up",
        parameters={"service_id": "svc-1"},
        version="v1",
    )
    return build_execution_contract(
        decision_contract=decision,
        execution_payload={"service_id": "svc-1", "action": "scale_up"},
        approved_by="sarathi",
        policy_snapshot=policy_snapshot,
    )


def test_semantic_guard_available_valid_transition_succeeds():
    """1. Semantic guard available + valid transition succeeds."""
    contract = _create_sample_contract()
    assert contract.execution_state == "APPROVED"
    advanced = advance_execution_state(contract, "EXECUTED")
    assert advanced.execution_state == "EXECUTED"
    assert advanced.execution_state_history == ("CREATED", "APPROVED", "EXECUTED")


def test_semantic_guard_available_invalid_transition_rejected():
    """2. Semantic guard available + invalid transition is rejected."""
    contract = _create_sample_contract()
    with pytest.raises(ValueError):
        # APPROVED -> COMPLETED is illegal in FSM
        advance_execution_state(contract, "COMPLETED")


def test_semantic_guard_import_failure_causes_transition_rejection():
    """3. Semantic guard import failure causes transition rejection (fail-closed)."""
    contract = _create_sample_contract()
    with patch.dict(sys.modules, {"control_plane.security.semantic_guard_engine": None}):
        with pytest.raises(RuntimeError) as exc_info:
            advance_execution_state(contract, "EXECUTED")
        assert "Semantic guard engine unavailable" in str(exc_info.value)


def test_semantic_guard_import_failure_no_state_history_mutation(monkeypatch):
    """4. Verify no state-history mutation and no lineage event on import failure."""
    contract = _create_sample_contract()
    initial_state = contract.execution_state
    initial_history = contract.execution_state_history

    lineage_events_emitted = []
    import control_plane.core.execution_lineage
    monkeypatch.setattr(
        control_plane.core.execution_lineage,
        "append_lineage_event",
        lambda *args, **kwargs: lineage_events_emitted.append((args, kwargs))
    )

    with patch.dict(sys.modules, {"control_plane.security.semantic_guard_engine": None}):
        with pytest.raises(RuntimeError):
            advance_execution_state(contract, "EXECUTED")

    # Contract state and history are unmodified
    assert contract.execution_state == initial_state
    assert contract.execution_state_history == initial_history
    # No lineage events were emitted for the failed transition
    assert len(lineage_events_emitted) == 0


def test_semantic_guard_unavailability_prevents_subsequent_execution():
    """5. Verify no execution can proceed through this transition boundary after guard unavailability."""
    contract = _create_sample_contract()
    with patch.dict(sys.modules, {"control_plane.security.semantic_guard_engine": None}):
        with pytest.raises(RuntimeError):
            advance_execution_state(contract, "EXECUTED")

    # Re-verify with guard still unavailable: cannot advance to any state
    with patch.dict(sys.modules, {"control_plane.security.semantic_guard_engine": None}):
        with pytest.raises(RuntimeError):
            advance_execution_state(contract, "FAILED")


# -----------------------------------------------------------------------------
# 2. POLICY SNAPSHOT — FAIL CLOSED
# -----------------------------------------------------------------------------
def test_valid_policy_snapshot_accepted():
    """1. Valid PolicySnapshot accepted."""
    ps = PolicySnapshot(policy_id="pol-1", policy_version="v1", policy_hash="h-abc")
    contract = _create_sample_contract(policy_snapshot=ps)
    assert contract.policy_snapshot == ps
    assert contract.policy_snapshot["policy_id"] == "pol-1"


def test_valid_dictionary_converts_correctly():
    """2. Valid dictionary converts correctly."""
    d = {"policy_id": "pol-2", "policy_version": "v1.2", "policy_hash": "h-def"}
    contract = _create_sample_contract(policy_snapshot=d)
    assert isinstance(contract.policy_snapshot, PolicySnapshot)
    assert contract.policy_snapshot["policy_id"] == "pol-2"
    assert contract.policy_snapshot["policy_version"] == "v1.2"
    assert contract.policy_snapshot["policy_hash"] == "h-def"


def test_malformed_dictionary_raises_explicit_validation_error():
    """3. Malformed dictionary raises explicit validation error."""
    # Missing required keys
    with pytest.raises(ValueError) as exc_1:
        _create_sample_contract(policy_snapshot={"policy_id": "pol-x"})
    assert "Malformed policy_snapshot" in str(exc_1.value)

    # Empty dict
    with pytest.raises(ValueError) as exc_2:
        _create_sample_contract(policy_snapshot={})
    assert "Malformed policy_snapshot" in str(exc_2.value)

    # None values for required keys
    with pytest.raises(ValueError) as exc_3:
        _create_sample_contract(policy_snapshot={"policy_id": None, "policy_version": "v1", "policy_hash": "h"})
    assert "Malformed policy_snapshot" in str(exc_3.value)

    # Non-dict type
    with pytest.raises(ValueError) as exc_4:
        _create_sample_contract(policy_snapshot="invalid-string-snapshot")
    assert "Malformed policy_snapshot" in str(exc_4.value)


def test_malformed_snapshot_cannot_produce_contract_with_none():
    """4. Malformed snapshot cannot produce an execution contract with policy_snapshot=None."""
    with pytest.raises(ValueError):
        _create_sample_contract(policy_snapshot={"bad": "payload"})


def test_direct_execution_contract_instantiation_field_validator():
    """4b. Direct ExecutionContract model instantiation enforces identical validation semantics."""
    decision = DecisionContract(
        decision_id="dec-direct",
        decision_type="execution",
        action="scale_up",
        parameters={"service_id": "svc-1"},
        version="v1",
    )
    # 1. Valid PolicySnapshot -> accepted
    ps = PolicySnapshot(policy_id="pol-1", policy_version="v1", policy_hash="h-1")
    c1 = ExecutionContract(
        execution_id="ex-direct-1",
        decision_contract=decision,
        execution_payload={"action": "scale_up"},
        execution_hash="some-hash",
        approved_at=1234567890,
        approved_by="sarathi",
        policy_snapshot=ps,
    )
    assert c1.policy_snapshot == ps

    # 2. Valid dict -> accepted and bound
    c2 = ExecutionContract(
        execution_id="ex-direct-2",
        decision_contract=decision,
        execution_payload={"action": "scale_up"},
        execution_hash="some-hash",
        approved_at=1234567890,
        approved_by="sarathi",
        policy_snapshot={"policy_id": "pol-2", "policy_version": "v1", "policy_hash": "h-2"},
    )
    assert isinstance(c2.policy_snapshot, PolicySnapshot)
    assert c2.policy_snapshot["policy_id"] == "pol-2"

    # 3. Malformed dict -> rejected
    with pytest.raises(ValueError) as exc1:
        ExecutionContract(
            execution_id="ex-direct-3",
            decision_contract=decision,
            execution_payload={"action": "scale_up"},
            execution_hash="some-hash",
            approved_at=1234567890,
            approved_by="sarathi",
            policy_snapshot={"invalid": "keys"},
        )
    assert "Malformed policy_snapshot" in str(exc1.value)

    # 4. Invalid type -> rejected
    with pytest.raises(ValueError) as exc2:
        ExecutionContract(
            execution_id="ex-direct-4",
            decision_contract=decision,
            execution_payload={"action": "scale_up"},
            execution_hash="some-hash",
            approved_at=1234567890,
            approved_by="sarathi",
            policy_snapshot=12345,
        )
    assert "Malformed policy_snapshot" in str(exc2.value)


def test_valid_snapshot_remains_cryptographically_bound():
    """5. Valid snapshot remains cryptographically bound exactly as before."""
    d = {"policy_id": "pol-bound", "policy_version": "v1", "policy_hash": "h-12345"}
    contract = _create_sample_contract(policy_snapshot=d)
    
    expected_hash = compute_execution_hash(
        decision_contract=contract.decision_contract,
        execution_payload=contract.execution_payload,
        execution_id=contract.execution_id,
        approved_at=contract.approved_at,
        approved_by=contract.approved_by,
        immutable=True,
        policy_snapshot=contract.policy_snapshot,
    )
    assert contract.execution_hash == expected_hash

    # Altering the snapshot invalidates hash
    altered_hash = compute_execution_hash(
        decision_contract=contract.decision_contract,
        execution_payload=contract.execution_payload,
        execution_id=contract.execution_id,
        approved_at=contract.approved_at,
        approved_by=contract.approved_by,
        immutable=True,
        policy_snapshot={"policy_id": "tampered", "policy_version": "v1", "policy_hash": "h-tampered"},
    )
    assert contract.execution_hash != altered_hash


# -----------------------------------------------------------------------------
# 3. TRACE CONSUMPTION — ANTI-REPLAY FAIL CLOSED
# -----------------------------------------------------------------------------
from security.trace_consumption import (
    TraceConsumptionRegistry,
    reset_trace_registry,
    is_trace_consumed,
    consume_trace,
)


def test_trace_consumption_normal_succeeds(tmp_path):
    """1. Normal consume succeeds."""
    store_file = str(tmp_path / "traces.json")
    registry = TraceConsumptionRegistry(store_file=store_file)
    assert registry.consume("trace-1") is True
    assert registry.is_consumed("trace-1") is True


def test_trace_consumption_second_consume_rejected(tmp_path):
    """2. Second consume is rejected."""
    store_file = str(tmp_path / "traces.json")
    registry = TraceConsumptionRegistry(store_file=store_file)
    assert registry.consume("trace-2") is True
    assert registry.consume("trace-2") is False


def test_trace_consumption_corrupted_persistence_fails_closed(tmp_path):
    """3. Corrupted persistence file fails closed."""
    store_file = str(tmp_path / "traces.json")
    with open(store_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json corrupted content ...")

    with pytest.raises(RuntimeError) as exc_info:
        TraceConsumptionRegistry(store_file=store_file)
    assert "unreadable or corrupted" in str(exc_info.value)


def test_trace_consumption_unreadable_schema_fails_closed(tmp_path):
    """4. Unreadable/invalid schema persistence file fails closed."""
    store_file = str(tmp_path / "traces.json")
    with open(store_file, "w", encoding="utf-8") as f:
        json.dump(["not", "a", "dict"], f)

    with pytest.raises(RuntimeError) as exc_info:
        TraceConsumptionRegistry(store_file=store_file)
    assert "unreadable or corrupted" in str(exc_info.value)


def test_trace_consumption_save_write_failure_full_pre_operation_rollback(tmp_path):
    """5. Save/write failure fails closed and restores complete pre-operation state."""
    store_file = str(tmp_path / "traces.json")
    registry = TraceConsumptionRegistry(store_file=store_file, ttl=10)
    
    # Establish pre-existing state with an active trace and an expired trace
    registry.consumed_traces = {"existing-trace", "expired-trace"}
    registry.timestamps = {
        "existing-trace": time.time(),
        "expired-trace": time.time() - 100,  # older than ttl
    }
    
    pre_traces_expected = set(registry.consumed_traces)
    pre_timestamps_expected = dict(registry.timestamps)

    with patch("os.replace", side_effect=OSError("Disk write protected")):
        with pytest.raises(RuntimeError) as exc_info:
            registry.consume("new-trace-fail")
        assert "Trace consumption persistence failed" in str(exc_info.value)

    # The entire pre-operation state must be restored, not just discarding new-trace-fail
    assert registry.consumed_traces == pre_traces_expected
    assert registry.timestamps == pre_timestamps_expected


def test_trace_consumption_restart_persistence_integrity(tmp_path):
    """6. Process-restart/load failure cannot make an already-consumed trace reusable."""
    store_file = str(tmp_path / "traces.json")
    reg1 = TraceConsumptionRegistry(store_file=store_file)
    assert reg1.consume("trace-reboot") is True

    # Restart simulated by new instance loading same store
    reg2 = TraceConsumptionRegistry(store_file=store_file)
    assert reg2.is_consumed("trace-reboot") is True
    assert reg2.consume("trace-reboot") is False


def test_trace_consumption_caller_chain_rejection():
    """8. Caller rejects the protected operation when the global singleton store is unavailable."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("executer_app_module", str(executer_dir / "app.py"))
    executer_app_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(executer_app_mod)
    executer_app = executer_app_mod.app
    executer_app.testing = False

    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as f:
        f.write("{ corrupt json ...")
        bad_store = f.name

    try:
        # Manipulate the exact global singleton used by the production caller
        reset_trace_registry(bad_store)
        client = executer_app.test_client()
        resp = client.post(
            "/execute-action",
            headers={"X-CALLER": "sarathi"},
            json={
                "service_id": "order-service",
                "action": "noop",
                "trace_id": "trace-test-corrupt-store",
                "execution_id": "exec-1",
                "execution_hash": "hash-1",
                "capability_id": "governed-execution",
            },
        )
        assert resp.status_code == 500
    finally:
        reset_trace_registry()  # reset to default
        if os.path.exists(bad_store):
            os.remove(bad_store)


# -----------------------------------------------------------------------------
# 4. NONCE STORE — REPLAY FAIL CLOSED
# -----------------------------------------------------------------------------
from security.nonce_store import (
    NonceStore,
    reset_nonce_store,
    check_nonce,
)


def test_nonce_store_normal_succeeds(tmp_path):
    """1. Normal nonce registration succeeds."""
    store_file = str(tmp_path / "nonces.json")
    store = NonceStore(store_file=store_file)
    assert store.check_and_store("nonce-1") is True
    assert store.is_valid("nonce-1") is False


def test_nonce_store_duplicate_rejected(tmp_path):
    """2. Duplicate nonce is rejected."""
    store_file = str(tmp_path / "nonces.json")
    store = NonceStore(store_file=store_file)
    assert store.check_and_store("nonce-2") is True
    assert store.check_and_store("nonce-2") is False


def test_nonce_store_corrupted_fails_closed(tmp_path):
    """3. Corrupted nonce store rejects protected request (raises RuntimeError)."""
    store_file = str(tmp_path / "nonces.json")
    with open(store_file, "w", encoding="utf-8") as f:
        f.write("corrupted {{{ nonce data")

    with pytest.raises(RuntimeError) as exc_info:
        NonceStore(store_file=store_file)
    assert "Nonce store unreadable or corrupted" in str(exc_info.value)


def test_nonce_store_unreadable_schema_fails_closed(tmp_path):
    """4. Unreadable schema nonce store rejects protected request."""
    store_file = str(tmp_path / "nonces.json")
    with open(store_file, "w", encoding="utf-8") as f:
        json.dump({"nonces": "not-a-list"}, f)

    with pytest.raises(RuntimeError) as exc_info:
        NonceStore(store_file=store_file)
    assert "Nonce store unreadable or corrupted" in str(exc_info.value)


def test_nonce_store_restart_preserves_history(tmp_path):
    """5. Restart does not forget valid nonce history."""
    store_file = str(tmp_path / "nonces.json")
    s1 = NonceStore(store_file=store_file)
    assert s1.check_and_store("nonce-reboot") is True

    s2 = NonceStore(store_file=store_file)
    assert s2.check_and_store("nonce-reboot") is False


def test_nonce_store_persistence_failure_full_pre_operation_rollback(tmp_path):
    """6. Persistence failure cannot silently permit nonce reuse or leave partial state."""
    store_file = str(tmp_path / "nonces.json")
    store = NonceStore(store_file=store_file, ttl=10)
    
    # Establish pre-existing state with active and expired nonces
    store.nonces = {"existing-nonce", "expired-nonce"}
    store.nonce_timestamps = {
        "existing-nonce": time.time(),
        "expired-nonce": time.time() - 100,
    }
    
    pre_nonces_expected = set(store.nonces)
    pre_timestamps_expected = dict(store.nonce_timestamps)

    with patch("os.replace", side_effect=OSError("Disk full")):
        with pytest.raises(RuntimeError) as exc_info:
            store.check_and_store("nonce-write-fail")
        assert "Nonce persistence failed" in str(exc_info.value)

    # In-memory store must restore complete pre-operation state
    assert store.nonces == pre_nonces_expected
    assert store.nonce_timestamps == pre_timestamps_expected


def test_nonce_store_caller_chain_rejection():
    """7. Caller rejects the request when the global singleton nonce storage is unavailable."""
    from executer.guard import validate_caller
    
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as f:
        f.write("{{{ broken nonces")
        bad_nonce_store = f.name

    try:
        # Manipulate the exact global singleton used by the production caller
        reset_nonce_store(bad_nonce_store)
        with pytest.raises(RuntimeError) as exc_info:
            validate_caller(
                payload={"action": "scale_up"},
                headers={
                    "X-Service-Id": "sarathi",
                    "X-Service-Timestamp": "1234567890",
                    "X-Service-Nonce": "nonce-fail-test",
                    "X-Service-Signature": "sig",
                }
            )
        assert "Nonce store unreadable or corrupted" in str(exc_info.value)
    finally:
        reset_nonce_store()
        if os.path.exists(bad_nonce_store):
            os.remove(bad_nonce_store)


# -----------------------------------------------------------------------------
# 5. DASHBOARD / AGGREGATE TELEMETRY
# -----------------------------------------------------------------------------
from control_plane.backend.app.main import (
    _calculate_aggregate_metrics,
    _build_live_dashboard_payload,
    prometheus_metrics,
    _INGESTED_LINKS,
)


def test_dashboard_psutil_failure_does_not_report_healthy(caplog):
    """1 & 2. psutil failure does not report HEALTHY and is observable."""
    with patch("psutil.cpu_percent", side_effect=Exception("cgroup error")):
        with patch("psutil.virtual_memory", side_effect=Exception("cgroup error")):
            with caplog.at_level(logging.WARNING):
                payload = _build_live_dashboard_payload()
    
    system_health = payload["system_health"]
    # Must NEVER be HEALTHY on monitoring failure
    assert system_health["status"] != "HEALTHY"
    assert system_health["status"] == "UNKNOWN"
    assert system_health["collection_status"] == "unavailable"
    assert system_health["cpu_utilization_pct"] is None
    # Must be observable in logs
    assert any("Live dashboard system health collection failed" in r.message for r in caplog.records)


def test_aggregate_metrics_git_failure_no_fabrication(caplog):
    """3. Git failure does not produce fabricated repository numbers."""
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
        with caplog.at_level(logging.WARNING):
            metrics = _calculate_aggregate_metrics()

    assert metrics["total_commits"] is None
    assert metrics["total_files"] is None
    assert metrics["total_contributors"] is None
    assert metrics["telemetry_status"]["git"] == "unavailable"
    assert any("git" in r.message.lower() for r in caplog.records)


def test_aggregate_metrics_coverage_failure_no_fabrication(caplog):
    """4. Coverage failure does not produce 78%."""
    with patch.dict(sys.modules, {"coverage": None}):
        with caplog.at_level(logging.WARNING):
            metrics = _calculate_aggregate_metrics()

    assert metrics["avg_test_coverage"] is None
    assert metrics["telemetry_status"]["coverage"] == "unavailable"


def test_aggregate_metrics_empty_links_no_fabricated_defaults():
    """5a. When no links are monitored, aggregate metrics exposes 0/None rather than fabricated 150/92."""
    with patch("control_plane.backend.app.main._INGESTED_LINKS", []):
        metrics = _calculate_aggregate_metrics()
        assert metrics["avg_response_time"] == 0
        assert metrics["total_errors"] == 0
        assert metrics["total_issues"] == 0
        assert metrics["avg_quality_score"] is None
        assert metrics["telemetry_status"]["link_heuristics"] == "no_links"


def test_prometheus_metrics_no_fabricated_measurements():
    """5b. Prometheus endpoint does not emit fabricated lines when metrics fail."""
    with patch("subprocess.run", side_effect=Exception("git missing")):
        with patch("psutil.cpu_percent", side_effect=Exception("psutil missing")):
            resp = prometheus_metrics()
            body = resp.body.decode("utf-8")
            # Should NOT emit fabricated commits or CPU lines
            assert "pravah_decision_brain_total_commits" not in body
            assert "pravah_decision_brain_cpu_percent" not in body
            # Up and links should still be emitted
            assert "pravah_decision_brain_up 1" in body


def test_normal_successful_telemetry():
    """6. Normal successful telemetry remains valid and unchanged."""
    with patch("psutil.cpu_percent", return_value=35.0):
        with patch("psutil.virtual_memory", return_value=MagicMock(percent=50.0)):
            payload = _build_live_dashboard_payload()
            assert payload["system_health"]["status"] == "HEALTHY"
            assert payload["system_health"]["cpu_utilization_pct"] == 35
            assert payload["system_health"]["memory_utilization_pct"] == 50
            assert payload["system_health"]["collection_status"] == "available"


# -----------------------------------------------------------------------------
# 6. SHAKTI EVENT AUDIT TRAIL & OBSERVER & EVIDENCE BUNDLE
# -----------------------------------------------------------------------------
from control_plane.api.agent_api import app as flask_agent_app


@pytest.fixture
def flask_client():
    flask_agent_app.config["TESTING"] = True
    with flask_agent_app.test_client() as client:
        yield client


def test_shakti_events_successful_append(flask_client):
    """6.1 Successful append returns existing success response."""
    headers = {
        "Authorization": "Bearer shakti-secret-key-change-in-prod",
        "X-Source-System": "SHAKTI",
    }
    payload = {
        "trace_id": "tr-shakti-ok",
        "correlation_id": "corr-1",
        "source": "shakti",
        "action": "scale_out",
        "event_type": "node_failure",
        "payload": {"details": "test"},
        "source_system": "SHAKTI",
        "published_at": "2026-09-07T00:00:00Z",
    }
    with patch("control_plane.api.agent_api.control_plane.append_decision_history", return_value=None):
        resp = flask_client.post("/pravah/api/v1/publish", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "CONNECTED"
        assert data["trace_id"] == "tr-shakti-ok"


def test_shakti_events_append_failure_returns_500_not_success(flask_client, caplog, tmp_path):
    """6.2 Append failure does not return false success (returns 500 error) using real I/O failure."""
    from control_plane.api.agent_api import control_plane
    headers = {
        "Authorization": "Bearer shakti-secret-key-change-in-prod",
        "X-Source-System": "SHAKTI",
    }
    payload = {
        "trace_id": "tr-shakti-fail",
        "correlation_id": "corr-2",
        "source": "shakti",
        "action": "scale_out",
        "event_type": "node_failure",
        "payload": {"details": "test"},
        "source_system": "SHAKTI",
        "published_at": "2026-09-07T00:00:00Z",
    }
    # Point history_file to an impossible path in an uncreated directory to cause real open() failure
    original_history = control_plane.history_file
    control_plane.history_file = str(tmp_path / "nonexistent_dir_123" / "unwritable_history.jsonl")
    try:
        with caplog.at_level(logging.ERROR):
            resp = flask_client.post("/pravah/api/v1/publish", json=payload, headers=headers)
            assert resp.status_code == 500
            data = resp.get_json()
            assert data["status"] == "error"
            assert "Audit persistence failed" in data["error"]
            assert any("Failed to append decision history" in r.message for r in caplog.records)
    finally:
        control_plane.history_file = original_history


def test_observer_forward_failure_does_not_fail_core_decision(flask_client, caplog):
    """7. Observer forwarding failure is logged and does not fail core decision."""
    from security.signing import sign_trace
    payload = {
        "app": "demo-app",
        "env": "dev",
        "state": "running",
        "trace_id": "tr-obs-test",
        "latency_ms": 50,
        "errors_last_min": 0,
        "workers": 2,
    }
    now_ts = str(int(time.time()))
    sig = sign_trace("tr-obs-test", now_ts, payload)
    headers = {
        "X-Trace-Id": "tr-obs-test",
        "X-Timestamp": now_ts,
        "X-Trace-Signature": sig,
    }
    with patch("requests.post", side_effect=Exception("Observer offline")):
        with caplog.at_level(logging.WARNING):
            resp = flask_client.post("/api/runtime", json=payload, headers=headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "success"
            assert any("Observer event forward failed" in r.message for r in caplog.records)


def test_evidence_bundle_save_failure_returns_500(flask_client, tmp_path):
    """8.1 Evidence bundle save failure returns 500 using real filesystem failure."""
    headers = {
        "Authorization": "Bearer shakti-secret-key-change-in-prod",
        "X-Source-System": "SHAKTI",
    }
    payload = {
        "bundle_id": "b-1",
        "trace_id": "tr-1",
        "execution_id": "ex-1",
        "decision_id": "dec-1",
        "decision_type": "governance",
        "authority_chain": ["auth-1"],
        "evidence": [{"item": "fact"}],
        "produced_at": "2026-09-07T00:00:00Z",
        "correlation_id": "corr-1",
        "source": "shakti",
        "action": "scale_out",
    }
    # Create an unwritable target by pointing to a path inside a non-directory file
    blocker_file = tmp_path / "blocker"
    blocker_file.write_text("not a directory")
    bad_store_path = str(blocker_file / "uncreatable" / "bundle.json")

    with patch("control_plane.api.agent_api.EVIDENCE_STORE_PATH", bad_store_path):
        resp = flask_client.post("/evidence", json=payload, headers=headers)
        assert resp.status_code == 500
        assert "Evidence persistence failed" in resp.get_json()["error"]


def test_evidence_bundle_corrupt_store_returns_500(flask_client, tmp_path):
    """8.2 Corrupted evidence bundle store causes retrieve to return 500."""
    headers = {
        "Authorization": "Bearer shakti-secret-key-change-in-prod",
        "X-Source-System": "SHAKTI",
    }
    bad_store = str(tmp_path / "corrupt_bundles.json")
    with open(bad_store, "w", encoding="utf-8") as f:
        f.write("{ not valid json ...")

    with patch("control_plane.api.agent_api.EVIDENCE_STORE_PATH", bad_store):
        resp = flask_client.get("/evidence/ev-nonexistent", headers=headers)
        assert resp.status_code == 500
        assert "Evidence store unavailable" in resp.get_json()["error"]


# -----------------------------------------------------------------------------
# 9. PHASE 2.5.4 REMOVAL OF SYNTHETIC EXTERNAL-LINK RESOURCE TELEMETRY
# -----------------------------------------------------------------------------
from control_plane.backend.app.schemas import LiveDashboardResponse, LiveDomainStatus
from control_plane.backend.app.main import (
    _build_live_dashboard_payload,
    INGESTED_RUNTIME_STATE,
    _INGESTED_LINKS,
)


def test_external_ingested_link_cpu_memory_is_none():
    """9.1 External ingested links without host agent/cgroup telemetry have cpu/memory as None."""
    sample_links = [
        {"name": "test-repo", "link": "https://github.com/org/test-repo", "status": "CONNECTED", "errors_24h": 0}
    ]
    with patch("control_plane.backend.app.main._INGESTED_LINKS", sample_links):
        with patch.dict(INGESTED_RUNTIME_STATE, {}, clear=True):
            payload = _build_live_dashboard_payload()
            services = payload["monitored_services"]
            assert len(services) == 1
            ext_service = services[0]
            assert ext_service["name"] == "test-repo"
            # Proven defect in Phase 2.5.3: cpu_percent was 15, memory_percent was 30
            assert ext_service["cpu_percent"] is None
            assert ext_service["memory_percent"] is None
            assert ext_service["cpu_percent"] != 15
            assert ext_service["memory_percent"] != 30
            assert ext_service["cpu_percent"] != 0


def test_runtime_compute_node_metrics_remain_numeric():
    """9.2 Genuine runtime compute nodes preserve their numeric CPU/memory telemetry."""
    runtime_state = {
        "compute-worker-1": {
            "metrics": {"cpu": 0.45, "memory": 0.65, "latency": 80, "error_rate": 0.0},
            "status": "RUNNING",
        },
        "compute-worker-2": {
            "metrics": {"cpu": 82, "memory": 91, "latency": 250, "error_rate": 0.05},
            "status": "DEGRADED",
        },
    }
    with patch("control_plane.backend.app.main._INGESTED_LINKS", []):
        with patch.dict(INGESTED_RUNTIME_STATE, runtime_state, clear=True):
            payload = _build_live_dashboard_payload()
            services = payload["monitored_services"]
            assert len(services) == 2
            s1 = next(s for s in services if s["name"] == "COMPUTE-WORKER-1")
            s2 = next(s for s in services if s["name"] == "COMPUTE-WORKER-2")
            # s1 cpu was 0.45 -> converted to 45
            assert s1["cpu_percent"] == 45
            assert s1["memory_percent"] == 65
            assert isinstance(s1["cpu_percent"], int)
            assert isinstance(s1["memory_percent"], int)
            # s2 cpu was 82 -> preserved as 82
            assert s2["cpu_percent"] == 82
            assert s2["memory_percent"] == 91
            assert isinstance(s2["cpu_percent"], int)
            assert isinstance(s2["memory_percent"], int)


def test_live_dashboard_payload_pydantic_serialization_with_none_resources():
    """9.3 LiveDashboardResponse and LiveDomainStatus validate and serialize nullable CPU/memory."""
    # Test LiveDomainStatus directly with None
    status_card = LiveDomainStatus(
        name="external-docs",
        domain="docs.example.com",
        url="https://docs.example.com",
        status="CONNECTED",
        health_score=95.0,
        response_time_ms=120,
        cpu_percent=None,
        memory_percent=None,
        uptime_percent=99.9,
        last_action="noop",
        errors_24h=0,
    )
    assert status_card.cpu_percent is None
    assert status_card.memory_percent is None
    dumped = status_card.model_dump()
    assert dumped["cpu_percent"] is None
    assert dumped["memory_percent"] is None

    # Test full LiveDashboardResponse validation from _build_live_dashboard_payload()
    sample_links = [
        {"name": "ext-service", "link": "https://github.com/org/repo", "status": "CONNECTED"}
    ]
    with patch("control_plane.backend.app.main._INGESTED_LINKS", sample_links):
        with patch.dict(INGESTED_RUNTIME_STATE, {}, clear=True):
            payload = _build_live_dashboard_payload()
            dashboard_model = LiveDashboardResponse.model_validate(payload)
            assert len(dashboard_model.monitored_services) == 1
            assert dashboard_model.monitored_services[0].cpu_percent is None
            assert dashboard_model.monitored_services[0].memory_percent is None

            # Verify JSON serialization succeeds
            json_payload = dashboard_model.model_dump_json()
            assert '"cpu_percent":null' in json_payload or '"cpu_percent": null' in json_payload
            assert '"memory_percent":null' in json_payload or '"memory_percent": null' in json_payload


def test_no_synthetic_15_30_values_for_external_links():
    """9.4 Verify that multiple external links never produce 15 or 30 fallback values."""
    diverse_links = [
        {"name": "alpha", "link": "https://github.com/org/alpha", "status": "CONNECTED"},
        {"name": "beta", "link": "https://gitlab.com/group/beta", "status": "CONNECTED"},
        {"name": "gamma", "link": "https://docs.pravah.io", "status": "CONNECTED"},
    ]
    with patch("control_plane.backend.app.main._INGESTED_LINKS", diverse_links):
        with patch.dict(INGESTED_RUNTIME_STATE, {}, clear=True):
            payload = _build_live_dashboard_payload()
            for service in payload["monitored_services"]:
                assert service["cpu_percent"] is None, f"{service['name']} has non-None CPU: {service['cpu_percent']}"
                assert service["memory_percent"] is None, f"{service['name']} has non-None memory: {service['memory_percent']}"
                assert service["cpu_percent"] != 15
                assert service["memory_percent"] != 30


def test_mixed_external_and_runtime_dashboard_payload():
    """9.5 Mixed dashboard contains both nullable external links and numeric compute nodes."""
    runtime_state = {
        "engine-1": {
            "metrics": {"cpu": 0.50, "memory": 0.70, "latency": 110, "error_rate": 0.0},
            "status": "RUNNING",
        }
    }
    sample_links = [
        {"name": "ext-api", "link": "https://api.external.com", "status": "CONNECTED"}
    ]
    with patch("control_plane.backend.app.main._INGESTED_LINKS", sample_links):
        with patch.dict(INGESTED_RUNTIME_STATE, runtime_state, clear=True):
            payload = _build_live_dashboard_payload()
            services = payload["monitored_services"]
            assert len(services) == 2

            runtime_svc = next(s for s in services if s["name"] == "ENGINE-1")
            ext_svc = next(s for s in services if s["name"] == "ext-api")

            assert runtime_svc["cpu_percent"] == 50
            assert runtime_svc["memory_percent"] == 70
            assert ext_svc["cpu_percent"] is None
            assert ext_svc["memory_percent"] is None


# -----------------------------------------------------------------------------
# 10. PHASE 2.5.6 REMAINING SILENT EXCEPTION BOUNDARY REMEDIATION
# -----------------------------------------------------------------------------
from control_plane.api.agent_api import app as agent_flask_app
from control_plane.backend.app.main import execute_action
import contracts.execution_contract as contract_module
import control_plane.core.execution_lineage as lineage_module
from control_plane.core.execution_lineage import LineageJournalState


def test_flask_metrics_clean_deployment_no_history_file(tmp_path, monkeypatch):
    """10.1 When decision history does not exist, /metrics returns standard clean baseline."""
    import control_plane.api.agent_api as agent_api_mod
    monkeypatch.setattr(agent_api_mod, "root_dir", str(tmp_path))

    with agent_flask_app.test_client() as client:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)

        assert "pravah_stability_score 100" in text
        assert "pravah_failures_total 0" in text
        assert "pravah_recoveries_total 0" in text
        assert "pravah_active_apps_total" in text


def test_flask_metrics_normal_history_computes_authentic_score(tmp_path, monkeypatch):
    """10.2 Flask /metrics endpoint calculates authentic metrics from valid decision history."""
    import control_plane.api.agent_api as agent_api_mod

    cp_dir = tmp_path / "logs" / "control_plane"
    cp_dir.mkdir(parents=True, exist_ok=True)
    target_history = cp_dir / "decision_history.jsonl"

    # 3 failure records, 0 recovery records
    # Stability = 100 - (3 * 2) + 0 = 94
    records = [
        {"action": "investigate", "state": "degraded"},
        {"action": "alert", "event_type": "crash"},
        {"action": "drain", "state": "degraded"},
    ]
    with open(target_history, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    monkeypatch.setattr(agent_api_mod, "root_dir", str(tmp_path))

    with agent_flask_app.test_client() as client:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)

        assert "pravah_failures_total 3" in text
        assert "pravah_recoveries_total 0" in text
        assert "pravah_stability_score 94" in text


def test_flask_metrics_corrupt_history_omits_score_and_logs_warning(tmp_path, monkeypatch, caplog):
    """10.3 Corrupt/malformed decision history must NOT emit fabricated 100 stability score and must log warning."""
    import control_plane.api.agent_api as agent_api_mod

    cp_dir = tmp_path / "logs" / "control_plane"
    cp_dir.mkdir(parents=True, exist_ok=True)
    bad_history = cp_dir / "decision_history.jsonl"
    bad_history.write_text('{"action": "scale_up", truncated_corrupt_data\n', encoding="utf-8")

    monkeypatch.setattr(agent_api_mod, "root_dir", str(tmp_path))

    with caplog.at_level(logging.WARNING):
        with agent_flask_app.test_client() as client:
            resp = client.get("/metrics")
            assert resp.status_code == 200
            text = resp.get_data(as_text=True)

            # Must NEVER emit fabricated 100 stability score
            assert "pravah_stability_score 100" not in text
            assert "pravah_stability_score " not in text

            # Must expose unavailable status
            assert 'pravah_stability_score_status{status="unavailable"} 1' in text
            assert "pravah_decision_history_parse_errors_total 1" in text

            # Must log warning
            assert any("Failed to parse decision history for metrics" in r.message for r in caplog.records)


def test_flask_metrics_unreadable_io_error_omits_score_and_logs_warning(tmp_path, monkeypatch, caplog):
    """10.4 Unreadable/locked decision history must NOT emit fabricated 100 stability score and must log warning."""
    import control_plane.api.agent_api as agent_api_mod

    cp_dir = tmp_path / "logs" / "control_plane"
    cp_dir.mkdir(parents=True, exist_ok=True)
    target_file = cp_dir / "decision_history.jsonl"
    target_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(agent_api_mod, "root_dir", str(tmp_path))

    real_open = open
    def mock_open_func(path, *args, **kwargs):
        if str(path).endswith("decision_history.jsonl"):
            raise OSError("Permission denied / file lock contention")
        return real_open(path, *args, **kwargs)

    with patch("builtins.open", side_effect=mock_open_func):
        with caplog.at_level(logging.WARNING):
            with agent_flask_app.test_client() as client:
                resp = client.get("/metrics")
                assert resp.status_code == 200
                text = resp.get_data(as_text=True)

                assert "pravah_stability_score 100" not in text
                assert "pravah_stability_score " not in text
                assert 'pravah_stability_score_status{status="unavailable"} 1' in text
                assert any("Failed to parse decision history for metrics: Permission denied" in r.message for r in caplog.records)


def test_execute_action_completion_transition_unwind_logs_warning(monkeypatch, tmp_path, caplog):
    """10.5 Secondary FAILED transition failure during completion error unwind logs warning and fails closed."""
    log_path = tmp_path / "execution_lineage.jsonl"
    monkeypatch.setattr(lineage_module, "get_lineage_log_path", lambda: log_path)
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX", {})
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX_LOADED", False)
    monkeypatch.setattr(lineage_module, "_LINEAGE_STATE", LineageJournalState.UNINITIALIZED)

    from control_plane.core.action_governance import ActionGovernance
    monkeypatch.setattr(ActionGovernance, "_load_state", lambda self: None)
    monkeypatch.setattr(ActionGovernance, "_save_state", lambda self: None)
    monkeypatch.setenv("ENVIRONMENT", "dev")

    orig_transition = contract_module.transition_contract_state

    def fail_on_completion_and_failed(contract, state, **kwargs):
        if state == "COMPLETED":
            raise RuntimeError("Simulated completion error")
        elif state == "FAILED" and contract.execution_state == "EXECUTED":
            raise RuntimeError("Simulated secondary FAILED transition unwind error")
        return orig_transition(contract, state, **kwargs)

    monkeypatch.setattr(contract_module, "transition_contract_state", fail_on_completion_and_failed)

    def mock_post(url, json=None, headers=None, **kwargs):
        req_payload = json or {}
        data = {
            "status": "executed",
            "execution_id": req_payload.get("execution_id", "test-exec"),
            "action": req_payload.get("action", "restart"),
            "service_id": req_payload.get("service_id", "svc-unwind-test"),
            "trace_id": req_payload.get("trace_id", "test-trace"),
            "execution_hash": req_payload.get("execution_hash", ""),
            "capability_id": req_payload.get("capability_id", "governed-execution"),
            "verified": True,
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = data
        return mock_resp

    monkeypatch.setattr("requests.post", mock_post)

    with caplog.at_level(logging.WARNING):
        allowed, response = execute_action("restart", "svc-unwind-test")

    assert allowed is False
    assert response["status"] == "failed"
    assert response["rejection_code"] == "COMPLETION_FAILED"
    assert any("Failed to record contract FAILED state during completion error unwind" in r.message for r in caplog.records)


def test_execute_action_error_unwind_logs_warning(monkeypatch, tmp_path, caplog):
    """10.6 Secondary FAILED transition failure during general error unwind logs warning and fails closed."""
    log_path = tmp_path / "execution_lineage.jsonl"
    monkeypatch.setattr(lineage_module, "get_lineage_log_path", lambda: log_path)
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX", {})
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX_LOADED", False)
    monkeypatch.setattr(lineage_module, "_LINEAGE_STATE", LineageJournalState.UNINITIALIZED)

    from control_plane.core.action_governance import ActionGovernance
    monkeypatch.setattr(ActionGovernance, "_load_state", lambda self: None)
    monkeypatch.setattr(ActionGovernance, "_save_state", lambda self: None)
    monkeypatch.setenv("ENVIRONMENT", "dev")

    orig_transition = contract_module.transition_contract_state

    def fail_on_failed_unwind(contract, state, **kwargs):
        if state == "FAILED":
            raise RuntimeError("Simulated secondary error during general error unwind")
        return orig_transition(contract, state, **kwargs)

    monkeypatch.setattr(contract_module, "transition_contract_state", fail_on_failed_unwind)

    def mock_post_raise(*args, **kwargs):
        raise ConnectionResetError("Simulated network drop to executor")

    monkeypatch.setattr("requests.post", mock_post_raise)

    with caplog.at_level(logging.WARNING):
        allowed, response = execute_action("restart", "svc-unwind-test-2")

    assert allowed is False
    assert response["status"] == "failed"
    assert response["rejection_code"] == "EXECUTION_EXCEPTION"
    assert any("Failed to record contract FAILED state during error unwind" in r.message for r in caplog.records)


