import copy

import pytest

from control_plane.core import execution_lineage as lineage_module
from control_plane.core.execution_lineage import append_lineage_event, replay_execution_lineage
from security.lineage_verifier import (
    DuplicateReplayError,
    PayloadHashMismatchError,
    SequenceViolationError,
    UnsignedReplayEventError,
    LineageVerifier,
)
from security.replay_verifier import ReplayVerificationMiddleware
from security.signed_trace import build_signed_trace, trace_hash


def _payload(execution_id, state, execution_hash="execution-hash", source="runtime", details=None):
    return {
        "execution_id": execution_id,
        "state": state,
        "execution_hash": execution_hash,
        "source": source,
        "details": details or {},
    }


def _event(trace, payload):
    event_hash = trace_hash(trace)
    return {
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
        "trace_hash": event_hash,
        "event_hash": event_hash,
    }


def _build_chain():
    execution_id = "execution-123"
    payload_1 = _payload(execution_id, "CREATED", execution_hash="hash-a")
    trace_1 = build_signed_trace(
        trace_id="trace-1",
        execution_id=execution_id,
        payload=payload_1,
        parent_hash="",
        signer="runtime",
        timestamp=10.0,
    )

    payload_2 = _payload(execution_id, "APPROVED", execution_hash="hash-a")
    trace_2 = build_signed_trace(
        trace_id="trace-2",
        execution_id=execution_id,
        payload=payload_2,
        parent_hash=trace_hash(trace_1),
        signer="runtime",
        timestamp=11.0,
    )

    event_1 = _event(trace_1, payload_1)
    event_2 = _event(trace_2, payload_2)
    return execution_id, (payload_1, payload_2), (event_1, event_2)


def test_signed_trace_is_deterministic():
    payload = _payload("execution-1", "CREATED", execution_hash="hash-a")
    trace_a = build_signed_trace(
        trace_id="trace-a",
        execution_id="execution-1",
        payload=payload,
        parent_hash="",
        signer="runtime",
        timestamp=123.0,
    )
    trace_b = build_signed_trace(
        trace_id="trace-a",
        execution_id="execution-1",
        payload=copy.deepcopy(payload),
        parent_hash="",
        signer="runtime",
        timestamp=123.0,
    )

    assert trace_a.payload_hash == trace_b.payload_hash
    assert trace_a.signature == trace_b.signature
    assert trace_hash(trace_a) == trace_hash(trace_b)


def test_lineage_verifier_accepts_valid_chain():
    _, payloads, events = _build_chain()

    assert LineageVerifier.verify_replay_chain(list(events), list(payloads)) is True
    assert ReplayVerificationMiddleware.verify_before_replay(list(events), list(payloads)) == {
        "status": "VERIFIED",
        "replay_safe": True,
    }


def test_replay_verifier_rejects_tampered_payload():
    _, payloads, events = _build_chain()
    first_event, second_event = events
    first_payload, second_payload = payloads

    with pytest.raises(PayloadHashMismatchError):
        LineageVerifier.verify_replay_chain(
            [first_event, second_event],
            [first_payload, {**second_payload, "details": {"tampered": True}}],
        )


def test_replay_verifier_rejects_missing_signature():
    _, payloads, events = _build_chain()
    first_event, second_event = events
    first_payload, second_payload = payloads

    with pytest.raises(UnsignedReplayEventError):
        LineageVerifier.verify_replay_chain(
            [first_event, {**second_event, "signature": ""}],
            [first_payload, second_payload],
        )


def test_replay_verifier_rejects_forged_parent_hash():
    _, payloads, events = _build_chain()
    first_event, second_event = events
    first_payload, second_payload = payloads

    with pytest.raises(UnsignedReplayEventError):
        LineageVerifier.verify_replay_chain(
            [first_event, {**second_event, "parent_hash": "fake-parent", "previous_hash": "fake-parent"}],
            [first_payload, second_payload],
        )


def test_replay_verifier_rejects_duplicate_replay():
    _, payloads, events = _build_chain()
    first_event, _ = events
    first_payload, _ = payloads

    with pytest.raises(DuplicateReplayError):
        LineageVerifier.verify_replay_chain([first_event, first_event], [first_payload, first_payload])


def test_reordered_events_fail_verification():
    _, payloads, events = _build_chain()
    first_event, second_event = events
    first_payload, second_payload = payloads

    with pytest.raises(SequenceViolationError):
        LineageVerifier.verify_replay_chain([second_event, first_event], [second_payload, first_payload])


def test_control_plane_replay_round_trip(monkeypatch, tmp_path):
    lineage_log = tmp_path / "execution_lineage.jsonl"
    monkeypatch.setattr(lineage_module, "get_lineage_log_path", lambda: lineage_log)
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX", {})
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX_LOADED", False)

    execution_id = "execution-round-trip"
    append_lineage_event(
        execution_id=execution_id,
        state="CREATED",
        execution_hash="hash-a",
        source="governance",
        details={"stage": "created"},
    )
    append_lineage_event(
        execution_id=execution_id,
        state="APPROVED",
        execution_hash="hash-a",
        source="governance",
        details={"stage": "approved"},
    )

    result = replay_execution_lineage(execution_id)

    assert result["valid"] is True
    assert result["execution_state_history"] == ["CREATED", "APPROVED"]
    assert len(result["events"]) == 2
    assert all(event.get("signature") for event in result["events"])
    assert all(event.get("trace_hash") for event in result["events"])
