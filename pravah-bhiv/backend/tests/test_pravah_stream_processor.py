"""
Tests for PRAVAH Stream Processor
Validates deterministic state transitions, FSM semantics, replay verification, and terminal state locks.
"""

import pytest
from pathlib import Path
from pravah.replay_ledger import ReplayLedger
from pravah.stream_processor import (
    StreamProcessor,
    InvalidStateTransitionError,
    TerminalStateLockedError,
)
from pravah.schema_validator import SchemaValidationError


@pytest.fixture
def isolated_processor(tmp_path):
    log_file = tmp_path / "proc_append_log.jsonl"
    index_file = tmp_path / "proc_replay_index.json"
    ledger = ReplayLedger(log_path=str(log_file), index_path=str(index_file))
    return StreamProcessor(ledger=ledger)


def test_full_lifecycle_created_to_completed(isolated_processor):
    exec_id = "exec-lifecycle-1"
    
    # 1. First event: triggers genesis CREATED then transitions to APPROVED
    s1 = {
        "schema_version": "1.0",
        "trace_id": "tr-1",
        "execution_id": exec_id,
        "timestamp": "2026-11-17T12:00:00Z",
        "source": "governance_agent",
        "signal_type": "execution",
        "payload": {"action": "approve"},
    }
    r1 = isolated_processor.process_signal(s1, target_state="APPROVED")
    assert r1["state"] == "APPROVED"
    assert r1["sequence"] == 2  # sequence 1 is CREATED (genesis)
    assert r1["schema_version"] == "1.0"
    assert len(r1["event_hash"]) == 64
    assert len(r1["state_hash"]) == 64

    # 2. Second event: APPROVED -> EXECUTED
    s2 = {
        "schema_version": "1.0",
        "trace_id": "tr-1",
        "execution_id": exec_id,
        "timestamp": "2026-11-17T12:00:01Z",
        "source": "executor_worker",
        "signal_type": "execution",
        "payload": {"action": "execute"},
    }
    r2 = isolated_processor.process_signal(s2, target_state="EXECUTED")
    assert r2["state"] == "EXECUTED"
    assert r2["sequence"] == 3
    assert r2["previous_hash"] == r1["event_hash"]

    # 3. Third event: EXECUTED -> COMPLETED
    s3 = {
        "schema_version": "1.0",
        "trace_id": "tr-1",
        "execution_id": exec_id,
        "timestamp": "2026-11-17T12:00:02Z",
        "source": "observer_service",
        "signal_type": "verification",
        "payload": {"status": "verified"},
    }
    r3 = isolated_processor.process_signal(s3, target_state="COMPLETED")
    assert r3["state"] == "COMPLETED"
    assert r3["sequence"] == 4

    # 4. Replay verification
    replay = isolated_processor.replay(exec_id)
    assert replay["is_valid"] is True
    assert replay["events_verified"] == 4
    assert replay["state_hash"] == r3["state_hash"]


def test_reject_illegal_transition_skip_approval(isolated_processor):
    exec_id = "exec-skip-test"
    
    # Attempting to go directly from genesis to EXECUTED without APPROVED
    s1 = {
        "schema_version": "1.0",
        "trace_id": "tr-2",
        "execution_id": exec_id,
        "timestamp": "2026-11-17T12:00:00Z",
        "source": "agent",
        "signal_type": "execution",
        "payload": {},
    }
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        isolated_processor.process_signal(s1, target_state="EXECUTED")
    assert "Invalid state transition" in str(exc_info.value)
    assert exc_info.value.error_code == "INVALID_STATE_TRANSITION"


def test_terminal_state_locked(isolated_processor):
    exec_id = "exec-terminal-lock"
    
    # Transition to COMPLETED
    s1 = {
        "schema_version": "1.0",
        "trace_id": "tr-3",
        "execution_id": exec_id,
        "timestamp": "2026-11-17T12:00:00Z",
        "source": "agent",
        "signal_type": "execution",
        "payload": {},
    }
    isolated_processor.process_signal(s1, target_state="APPROVED")
    isolated_processor.process_signal(s1, target_state="EXECUTED")
    isolated_processor.process_signal(s1, target_state="COMPLETED")

    # Attempt any further event
    s_extra = {
        "schema_version": "1.0",
        "trace_id": "tr-3",
        "execution_id": exec_id,
        "timestamp": "2026-11-17T12:00:10Z",
        "source": "agent",
        "signal_type": "execution",
        "payload": {"action": "late_event"},
    }
    with pytest.raises(TerminalStateLockedError) as exc_info:
        isolated_processor.process_signal(s_extra, target_state="APPROVED")
    assert "terminal state 'COMPLETED'" in str(exc_info.value)


def test_transition_to_failed_state(isolated_processor):
    exec_id = "exec-failure-test"
    
    s1 = {
        "schema_version": "1.0",
        "trace_id": "tr-4",
        "execution_id": exec_id,
        "timestamp": "2026-11-17T12:00:00Z",
        "source": "agent",
        "signal_type": "execution",
        "payload": {},
    }
    isolated_processor.process_signal(s1, target_state="APPROVED")

    # Now fail from APPROVED
    s_fail = {
        "schema_version": "1.0",
        "trace_id": "tr-4",
        "execution_id": exec_id,
        "timestamp": "2026-11-17T12:00:01Z",
        "source": "agent",
        "signal_type": "execution",
        "payload": {"error": "hardware failure"},
    }
    rf = isolated_processor.process_signal(s_fail, target_state="FAILED")
    assert rf["state"] == "FAILED"

    # Terminal lock applies to FAILED
    with pytest.raises(TerminalStateLockedError):
        isolated_processor.process_signal(s_fail, target_state="COMPLETED")


def test_batch_stream_processing(isolated_processor):
    exec_id = "exec-batch-stream"
    
    signals = [
        {
            "schema_version": "1.0",
            "trace_id": "tr-batch",
            "execution_id": exec_id,
            "timestamp": f"2026-11-17T12:00:0{i}Z",
            "source": "batch_producer",
            "signal_type": "execution",
            "payload": {"target_state": state},
        }
        for i, state in enumerate(["APPROVED", "EXECUTED", "COMPLETED"], start=1)
    ]

    results = isolated_processor.process_stream(signals)
    assert len(results) == 3
    assert [r["state"] for r in results] == ["APPROVED", "EXECUTED", "COMPLETED"]

    state = isolated_processor.get_state(exec_id)
    assert state["current_state"] == "COMPLETED"
    assert state["sequence"] == 4


def test_cross_instance_determinism(tmp_path):
    """
    Two distinct StreamProcessor instances processing identical events from fresh state
    must generate byte-for-byte identical state hashes and event hashes.
    """
    signals = [
        {
            "schema_version": "1.0",
            "trace_id": "tr-determ",
            "execution_id": "exec-determ-1",
            "timestamp": "2026-11-17T12:00:01Z",
            "source": "governance",
            "signal_type": "execution",
            "payload": {"step": "approve", "target_state": "APPROVED"},
        },
        {
            "schema_version": "1.0",
            "trace_id": "tr-determ",
            "execution_id": "exec-determ-1",
            "timestamp": "2026-11-17T12:00:02Z",
            "source": "executor",
            "signal_type": "execution",
            "payload": {"step": "execute", "target_state": "EXECUTED"},
        },
        {
            "schema_version": "1.0",
            "trace_id": "tr-determ",
            "execution_id": "exec-determ-1",
            "timestamp": "2026-11-17T12:00:03Z",
            "source": "observer",
            "signal_type": "verification",
            "payload": {"step": "complete", "target_state": "COMPLETED"},
        },
    ]

    # Instance A
    ledger_a = ReplayLedger(str(tmp_path / "a.jsonl"), str(tmp_path / "a_idx.json"))
    proc_a = StreamProcessor(ledger=ledger_a)
    results_a = proc_a.process_stream(signals)

    # Instance B
    ledger_b = ReplayLedger(str(tmp_path / "b.jsonl"), str(tmp_path / "b_idx.json"))
    proc_b = StreamProcessor(ledger=ledger_b)
    results_b = proc_b.process_stream(signals)

    assert len(results_a) == len(results_b)
    for ra, rb in zip(results_a, results_b):
        assert ra["event_hash"] == rb["event_hash"]
        assert ra["state_hash"] == rb["state_hash"]
        assert ra["state"] == rb["state"]
        assert ra["sequence"] == rb["sequence"]

    assert proc_a.get_state("exec-determ-1")["state_hash"] == proc_b.get_state("exec-determ-1")["state_hash"]
