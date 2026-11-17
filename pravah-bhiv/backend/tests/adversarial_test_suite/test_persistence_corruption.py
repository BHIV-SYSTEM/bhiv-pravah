from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from control_plane.core import execution_lineage as lineage_module
from control_plane.core.execution_lineage import (
    LineageJournalState,
    append_lineage_event,
    replay_execution_lineage,
    reset_lineage_journal_state,
    _read_events,
)
from control_plane.backend.app.main import app
from security.lineage_verifier import LineagePersistenceCorruptionError


def _setup_isolated_journal(monkeypatch, tmp_path: Path) -> Path:
    log_path = tmp_path / "execution_lineage.jsonl"
    monkeypatch.setattr(lineage_module, "get_lineage_log_path", lambda: log_path)
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX", {})
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX_LOADED", False)
    monkeypatch.setattr(lineage_module, "_LINEAGE_STATE", LineageJournalState.UNINITIALIZED)
    return log_path


def test_read_events_raises_on_malformed_json(monkeypatch, tmp_path):
    """Test A: Proves that _read_events raises LineagePersistenceCorruptionError on malformed JSON and exposes the line number."""
    log_path = _setup_isolated_journal(monkeypatch, tmp_path)

    # Line 1 is valid, Line 2 is malformed
    valid_record = {"execution_id": "test-1", "state": "CREATED", "event_id": "e1"}
    log_path.write_text(
        json.dumps(valid_record) + "\n" + '{"execution_id": "test-1", broken_syntax\n',
        encoding="utf-8",
    )

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        _read_events()

    err = exc_info.value
    assert err.line_number == 2
    assert err.line_hash is not None
    assert len(err.line_hash) == 64  # SHA-256 hex digest
    assert err.excerpt is not None


def test_read_events_raises_on_truncated_bytes(monkeypatch, tmp_path):
    """Test B: Proves that truncated JSON lines (partial writes at EOF) are detected."""
    log_path = _setup_isolated_journal(monkeypatch, tmp_path)

    # Valid records followed by truncated write at EOF
    rec1 = {"execution_id": "test-2", "state": "CREATED", "event_id": "e1"}
    rec2 = {"execution_id": "test-2", "state": "APPROVED", "event_id": "e2"}
    truncated_tail = '{"execution_id": "test-2", "state": "EXEC'

    log_path.write_text(
        json.dumps(rec1) + "\n" + json.dumps(rec2) + "\n" + truncated_tail,
        encoding="utf-8",
    )

    with pytest.raises(LineagePersistenceCorruptionError) as exc_info:
        _read_events()

    assert exc_info.value.line_number == 3


def test_replay_returns_invalid_on_nonexistent_execution(monkeypatch, tmp_path):
    """Test C: Proves that querying a nonexistent execution on an intact journal returns valid=False and error=EXECUTION_NOT_FOUND."""
    log_path = _setup_isolated_journal(monkeypatch, tmp_path)

    # Write a valid execution into the journal
    append_lineage_event("exec-existing", "CREATED", "hash-1", "runtime")

    result = replay_execution_lineage("nonexistent-id")

    assert result["valid"] is False
    assert result["error"] == "EXECUTION_NOT_FOUND"
    assert result["events"] == []
    assert result["final_state"] is None
    assert result["execution_state_history"] == []


def test_api_verify_returns_invalid_on_empty_execution(monkeypatch, tmp_path):
    """Test D: Proves that GET /api/lineage/{id}/verify returns valid=False, hash_chain_valid=False for nonexistent executions."""
    _setup_isolated_journal(monkeypatch, tmp_path)

    client = TestClient(app)
    response = client.get("/api/lineage/missing-execution-123/verify")

    assert response.status_code == 200
    data = response.json()
    assert data["execution_id"] == "missing-execution-123"
    assert data["valid"] is False
    assert data["hash_chain_valid"] is False
    assert data["fsm_valid"] is False
    assert data["error"] == "EXECUTION_NOT_FOUND"


def test_tail_corruption_blocks_lineage_branching(monkeypatch, tmp_path):
    """Test E: Proves that tail corruption prevents appending and prevents lineage history branching."""
    log_path = _setup_isolated_journal(monkeypatch, tmp_path)
    execution_id = "exec-tail-corrupt"

    # Step 1: Write valid initial events
    append_lineage_event(execution_id, "CREATED", "hash-1", "runtime")
    append_lineage_event(execution_id, "APPROVED", "hash-2", "runtime")

    # Step 2: Inject corrupted tail record (simulating partial write/crash at EOF)
    with log_path.open("a", encoding="utf-8") as f:
        f.write('{"event_id": "corrupted", "state": "EXEC\n')

    original_content = log_path.read_text(encoding="utf-8")

    # Step 3: Reset in-memory state (simulating system restart after crash)
    reset_lineage_journal_state()
    monkeypatch.setattr(lineage_module, "get_lineage_log_path", lambda: log_path)

    # Step 4: Attempt to append a new event (e.g. runtime attempting to resume)
    with pytest.raises(LineagePersistenceCorruptionError):
        append_lineage_event(execution_id, "EXECUTING", "hash-3", "runtime")

    # Step 5: Verify that the corrupted journal was NOT modified or branched
    current_content = log_path.read_text(encoding="utf-8")
    assert current_content == original_content


def test_clean_journal_roundtrip_passes(monkeypatch, tmp_path):
    """Test F: Proves that clean lineages continue to append, replay, and verify deterministically with valid=True."""
    log_path = _setup_isolated_journal(monkeypatch, tmp_path)
    execution_id = "exec-clean-roundtrip"

    append_lineage_event(execution_id, "CREATED", "hash-a", "governance", details={"stage": "start"})
    append_lineage_event(execution_id, "APPROVED", "hash-a", "governance", details={"stage": "review"})
    append_lineage_event(execution_id, "EXECUTED", "hash-a", "runtime", details={"stage": "run"})

    result = replay_execution_lineage(execution_id)

    assert result["valid"] is True
    assert result["execution_id"] == execution_id
    assert result["final_state"] == "EXECUTED"
    assert len(result["events"]) == 3
    assert result["execution_state_history"] == ["CREATED", "APPROVED", "EXECUTED"]
    assert all(event.get("signature") for event in result["events"])
    assert all(event.get("trace_hash") for event in result["events"])
