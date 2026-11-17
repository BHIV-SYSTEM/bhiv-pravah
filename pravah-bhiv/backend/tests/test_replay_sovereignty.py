import sys
import os
import copy
import time
import pytest
from unittest.mock import patch

# Adjust sys.path to resolve root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from security.signing import sign_service_request, verify_service_request, sign_payload, verify_payload
from security.internal_requests import build_signed_headers
from security.nonce_store import check_nonce
from security.trace_consumption import is_trace_consumed, consume_trace
from security.lineage_verifier import (
    LineageVerifier,
    SequenceViolationError,
    PayloadHashMismatchError,
    UnsignedReplayEventError
)
from security.signed_trace import build_signed_trace, trace_hash

# Import executer app (check both nested and root layouts)
nested_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../reliability-controller2-main/executer'))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../reliability-controller2-main/executer'))
sys.path.insert(0, nested_path if os.path.exists(nested_path) else root_path)
from app import app


def test_first_state_must_be_created():
    """Verify that a replay chain must start with a CREATED state."""
    payload = {
        "execution_id": "exec-abc",
        "state": "APPROVED",
        "execution_hash": "hash-1",
        "source": "runtime",
        "details": {}
    }
    trace = build_signed_trace(
        trace_id="trace-abc",
        execution_id="exec-abc",
        payload=payload,
        parent_hash="",
        signer="runtime",
        timestamp=time.time()
    )
    
    event = {
        "event_id": trace.trace_id,
        "trace_id": trace.trace_id,
        "execution_id": trace.execution_id,
        "previous_hash": trace.parent_hash,
        "parent_hash": trace.parent_hash,
        "timestamp": trace.timestamp,
        "state": payload["state"],
        "execution_hash": payload["execution_hash"],
        "source": payload["source"],
        "details": payload["details"],
        "payload_hash": trace.payload_hash,
        "signer": trace.signer,
        "signature": trace.signature,
        "trace_hash": trace_hash(trace)
    }
    
    with pytest.raises(SequenceViolationError, match="REPLAY_REJECTED_MUST_START_WITH_CREATED"):
        LineageVerifier.verify_replay_chain([event], [payload])


def test_single_use_trace_protection(tmp_path):
    """Verify that a trace ID can only be consumed once."""
    test_store = str(tmp_path / "test_trace_consumption.json")
    from security.trace_consumption import TraceConsumptionRegistry
    registry = TraceConsumptionRegistry(store_file=test_store)
    
    trace_id = "test-unique-trace-123"
    
    # Not consumed initially
    assert not registry.is_consumed(trace_id)
    
    # First consume should succeed
    assert registry.consume(trace_id) is True
    
    # Consumed now
    assert registry.is_consumed(trace_id)
    
    # Second consume should fail
    assert registry.consume(trace_id) is False


def test_payload_tampering_invalidates_signature():
    """Verify that modifying any arguments in the payload invalidates the signature verification."""
    payload = {
        "execution_id": "exec-1",
        "state": "CREATED",
        "execution_hash": "hash-a",
        "source": "governance",
        "details": {"key": "value"}
    }
    
    signed = sign_payload(payload)
    assert verify_payload(signed) is True
    
    # Tamper details
    tampered_details = copy.deepcopy(signed)
    tampered_details["details"]["key"] = "tampered"
    assert verify_payload(tampered_details) is False
    
    # Tamper state
    tampered_state = copy.deepcopy(signed)
    tampered_state["state"] = "APPROVED"
    assert verify_payload(tampered_state) is False


def test_executer_app_endpoints(tmp_path):
    """Verify that the execution server enforces signature, replay, and trace consumption checks."""
    app.config["TESTING"] = True
    client = app.test_client()
    
    from security.nonce_store import NonceStore
    from security.trace_consumption import TraceConsumptionRegistry
    
    test_nonce_file = str(tmp_path / "test_nonce_store.json")
    test_trace_file = str(tmp_path / "test_trace_store.json")
    
    mock_nonce_store = NonceStore(store_file=test_nonce_file)
    mock_trace_registry = TraceConsumptionRegistry(store_file=test_trace_file)
    
    with patch("app.check_nonce", side_effect=mock_nonce_store.check_and_store), \
         patch("app.is_trace_consumed", side_effect=mock_trace_registry.is_consumed), \
         patch("app.consume_trace", side_effect=mock_trace_registry.consume), \
         patch("app.validate_deployment_request", return_value="ALLOW"), \
         patch("app.execute_action", return_value={"status": "success", "output": "patched", "error": "", "latency": 0.1}), \
         patch.dict("app.cooldowns", {}, clear=True), \
         patch("app.COOLDOWN_TIME", 0), \
         patch("requests.post") as mock_post:
        
        # 1. Dev environment fallback: allows no signature headers if X-CALLER = sarathi
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            response = client.post(
                "/execute-action",
                headers={"X-CALLER": "sarathi"},
                json={
                    "trace_id": "t1",
                    "service_id": "web1-blue",
                    "action": "restart",
                    "execution_id": "exec-t1",
                    "execution_hash": "hash-t1",
                    "capability_id": "governed-execution",
                }
            )
            assert response.status_code == 200
            assert mock_trace_registry.is_consumed("t1")
            
        # 2. Prod environment: requires signature headers
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            # Request without signature headers should be rejected
            response = client.post(
                "/execute-action",
                headers={"X-CALLER": "sarathi"},
                json={
                    "trace_id": "t2",
                    "service_id": "web1-blue",
                    "action": "restart",
                    "execution_id": "exec-t2",
                    "execution_hash": "hash-t2",
                    "capability_id": "governed-execution",
                }
            )
            assert response.status_code == 401
            assert any(msg in response.data for msg in [b"Missing service id", b"missing signature headers"])
            
            # Request with valid signature headers should succeed
            payload = {
                "trace_id": "t2",
                "service_id": "web1-blue",
                "action": "restart",
                "execution_id": "exec-t2",
                "execution_hash": "hash-t2",
                "capability_id": "governed-execution",
            }
            headers = build_signed_headers("sarathi", payload)
            
            response = client.post(
                "/execute-action",
                headers=headers,
                json=payload
            )
            assert response.status_code == 200
            assert mock_trace_registry.is_consumed("t2")
            
            # 3. Duplicate trace ID rejection
            payload_dup = {
                "trace_id": "t2",
                "service_id": "web1-blue",
                "action": "restart",
                "execution_id": "exec-t2",
                "execution_hash": "hash-t2",
                "capability_id": "governed-execution",
            }
            headers_dup = build_signed_headers("sarathi", payload_dup)
            
            response = client.post(
                "/execute-action",
                headers=headers_dup,
                json=payload_dup
            )
            assert response.status_code == 400
            assert b"already consumed" in response.data
            
            # 4. Duplicate nonce rejection
            payload_nonce = {
                "trace_id": "t3",
                "service_id": "web1-blue",
                "action": "restart",
                "execution_id": "exec-t3",
                "execution_hash": "hash-t3",
                "capability_id": "governed-execution",
            }
            headers_nonce = build_signed_headers("sarathi", payload_nonce)
            
            # First request with this nonce should succeed
            response = client.post(
                "/execute-action",
                headers=headers_nonce,
                json=payload_nonce
            )
            assert response.status_code == 200
            
            # Second request with the same nonce but different trace should fail due to duplicate nonce
            payload_nonce_2 = {
                "trace_id": "t4",
                "service_id": "web1-blue",
                "action": "restart",
                "execution_id": "exec-t4",
                "execution_hash": "hash-t4",
                "capability_id": "governed-execution",
            }
            ts = headers_nonce['X-Service-Timestamp']
            nonce = headers_nonce['X-Service-Nonce']
            sig = sign_service_request("sarathi", ts, nonce, payload_nonce_2)
            
            bad_headers = {
                "X-Service-Id": "sarathi",
                "X-Service-Timestamp": ts,
                "X-Service-Nonce": nonce,
                "X-Service-Signature": sig
            }
            
            response = client.post(
                "/execute-action",
                headers=bad_headers,
                json=payload_nonce_2
            )
            assert response.status_code == 401
            assert any(msg in response.data for msg in [b"Replay attack detected", b"duplicate nonce"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
