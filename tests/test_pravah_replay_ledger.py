"""
Tests for Replay Ledger Layer
Validates append-only storage, hash-chain integrity, tamper detection, and deterministic replay.
"""

import json
import pytest
from pathlib import Path
from pravah.replay_ledger import (
    ReplayLedger,
    ReplayTamperingError,
    compute_canonical_hash,
)


@pytest.fixture
def temp_ledger(tmp_path):
    log_file = tmp_path / "test_append_log.jsonl"
    index_file = tmp_path / "test_replay_index.json"
    return ReplayLedger(log_path=str(log_file), index_path=str(index_file))


def test_append_only_monotonic_sequence(temp_ledger):
    exec_id = "test-exec-1"
    
    e1 = temp_ledger.record_event(
        execution_id=exec_id,
        event_id="e1",
        state="CREATED",
        timestamp=1000,
        source="unit_test",
        details={"step": "init"},
        previous_hash="",
    )
    assert e1.sequence == 1
    assert e1.previous_hash == ""
    assert len(e1.event_hash) == 64

    e2 = temp_ledger.record_event(
        execution_id=exec_id,
        event_id="e2",
        state="APPROVED",
        timestamp=1001,
        source="unit_test",
        details={"step": "approve"},
        previous_hash=e1.event_hash,
    )
    assert e2.sequence == 2
    assert e2.previous_hash == e1.event_hash

    # Check journal file lines
    with open(temp_ledger.log_path, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == 2


def test_append_only_preserves_historical_events(temp_ledger):
    exec_id = "test-exec-preserve"
    
    e1 = temp_ledger.record_event(
        execution_id=exec_id,
        event_id="e1",
        state="CREATED",
        timestamp=2000,
        source="unit_test",
        details={"val": 42},
    )

    with open(temp_ledger.log_path, "r") as f:
        first_line_snapshot = f.readline()

    # Append second event
    temp_ledger.record_event(
        execution_id=exec_id,
        event_id="e2",
        state="APPROVED",
        timestamp=2001,
        source="unit_test",
        details={"val": 43},
    )

    with open(temp_ledger.log_path, "r") as f:
        first_line_after = f.readline()

    # The historical line must be identical byte-for-byte
    assert first_line_snapshot == first_line_after


def test_hash_chain_continuity_and_verification(temp_ledger):
    exec_id = "test-exec-chain"
    
    e1 = temp_ledger.record_event(exec_id, "e1", "CREATED", 3000, "test", {"msg": "genesis"})
    e2 = temp_ledger.record_event(exec_id, "e2", "APPROVED", 3001, "test", {"msg": "approved"})
    e3 = temp_ledger.record_event(exec_id, "e3", "EXECUTED", 3002, "test", {"msg": "executed"})
    e4 = temp_ledger.record_event(exec_id, "e4", "COMPLETED", 3003, "test", {"msg": "done"})

    v = temp_ledger.verify_replay(exec_id)
    assert v["is_valid"] is True
    assert v["events_verified"] == 4
    assert v["status"] == "VALID"
    assert len(v["state_hash"]) == 64
    assert temp_ledger.is_tampered(exec_id) is False


def test_tamper_detection_on_corrupted_journal(temp_ledger):
    exec_id = "test-exec-tamper"
    
    temp_ledger.record_event(exec_id, "e1", "CREATED", 4000, "test", {"val": 1})
    temp_ledger.record_event(exec_id, "e2", "APPROVED", 4001, "test", {"val": 2})

    # Tamper with the journal file by replacing content in line 1
    with open(temp_ledger.log_path, "r") as f:
        lines = f.readlines()

    tampered_record = json.loads(lines[0])
    # Alter payload details without updating hashes
    tampered_record["event"]["details"]["val"] = 9999
    lines[0] = json.dumps(tampered_record) + "\n"

    with open(temp_ledger.log_path, "w") as f:
        f.writelines(lines)

    # Re-initialize ledger to force reload
    reloaded_ledger = ReplayLedger(str(temp_ledger.log_path), str(temp_ledger.index_path))
    v = reloaded_ledger.verify_replay(exec_id)

    # Must detect tampering
    assert v["is_valid"] is False
    assert v["status"] in {"PAYLOAD_CORRUPTION", "HASH_MISMATCH", "CHAIN_BREAK"}
    assert reloaded_ledger.is_tampered(exec_id) is True


def test_reject_mismatched_previous_hash(temp_ledger):
    exec_id = "test-exec-bad-prev"
    
    temp_ledger.record_event(exec_id, "e1", "CREATED", 5000, "test", {"step": 1})

    # Try to append with fraudulent previous_hash
    with pytest.raises(ReplayTamperingError) as exc_info:
        temp_ledger.record_event(
            execution_id=exec_id,
            event_id="e2",
            state="APPROVED",
            timestamp=5001,
            source="test",
            details={"step": 2},
            previous_hash="0" * 64,  # Fraudulent
        )
    assert "Hash chain break" in str(exc_info.value)


def test_state_reconstruction(temp_ledger):
    exec_id = "test-exec-reconstruct"
    
    temp_ledger.record_event(exec_id, "e1", "CREATED", 6000, "test", {})
    temp_ledger.record_event(exec_id, "e2", "APPROVED", 6001, "test", {})
    temp_ledger.record_event(exec_id, "e3", "EXECUTED", 6002, "test", {})
    temp_ledger.record_event(exec_id, "e4", "COMPLETED", 6003, "test", {})

    state = temp_ledger.reconstruct_state(exec_id)
    assert state["current_state"] == "COMPLETED"
    assert state["sequence"] == 4
    assert state["state_history"] == ["CREATED", "APPROVED", "EXECUTED", "COMPLETED"]
    assert state["is_terminal"] is True
