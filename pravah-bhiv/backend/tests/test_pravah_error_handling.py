"""
Negative and Exception Handling Tests for PRAVAH Stream Processor & Replay Ledger
Validates robust exception handling, structured error objects, fail-closed boundaries, and error sanitization.
"""

import pytest
from pathlib import Path
from pravah.replay_ledger import ReplayLedger, ReplayTamperingError
from pravah.stream_processor import (
    StreamProcessor,
    InvalidStateTransitionError,
    TerminalStateLockedError,
)
from pravah.schema_validator import (
    SchemaValidatorV1,
    SchemaValidationError,
    ValidationErrorCode,
)


@pytest.fixture
def err_processor(tmp_path):
    log_file = tmp_path / "err_log.jsonl"
    index_file = tmp_path / "err_idx.json"
    ledger = ReplayLedger(log_path=str(log_file), index_path=str(index_file))
    return StreamProcessor(ledger=ledger)


def test_schema_validation_error_structure():
    malformed = {
        "schema_version": "1.0",
        # missing trace_id
        "execution_id": "exec-err-1",
        "timestamp": "2026-11-17T12:00:00Z",
        "source": "tester",
        "signal_type": "execution",
        "payload": {},
    }
    with pytest.raises(SchemaValidationError) as exc_info:
        SchemaValidatorV1.enforce_inbound(malformed)

    err = exc_info.value
    res = err.validation_result
    assert res.valid is False
    assert len(res.errors) >= 1
    assert any(e.field == "trace_id" and e.error_code == ValidationErrorCode.MISSING_REQUIRED_FIELD for e in res.errors)


def test_stream_processor_handles_malformed_input_gracefully(err_processor):
    bad_signal = {"schema_version": "0.9"}  # Invalid version, missing fields
    with pytest.raises(SchemaValidationError):
        err_processor.process_signal(bad_signal)


def test_nonexistent_execution_replay(err_processor):
    res = err_processor.replay("non-existent-exec-id")
    assert res["is_valid"] is False
    assert res["status"] == "NOT_FOUND"
    assert "No events recorded" in res["error"]


def test_error_details_structured_and_sanitized(err_processor):
    signal = {
        "schema_version": "1.0",
        "trace_id": "tr-err",
        "execution_id": "exec-sanitized",
        "timestamp": "2026-11-17T12:00:00Z",
        "source": "tester",
        "signal_type": "execution",
        "payload": {"secret_token": "SUPER_SECRET_12345"},
    }
    # Skip approved -> directly go to COMPLETED
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        err_processor.process_signal(signal, target_state="COMPLETED")

    err_dict = exc_info.value.to_dict()
    assert err_dict["error_code"] == "INVALID_STATE_TRANSITION"
    assert "SUPER_SECRET_12345" not in err_dict["message"]


def test_ledger_tampering_exception_attributes(tmp_path):
    log_file = tmp_path / "tamper_attr.jsonl"
    index_file = tmp_path / "tamper_attr_idx.json"
    ledger = ReplayLedger(log_path=str(log_file), index_path=str(index_file))

    ledger.record_event("exec-t1", "e1", "CREATED", 1000, "test", {})
    
    with pytest.raises(ReplayTamperingError) as exc_info:
        ledger.record_event(
            execution_id="exec-t1",
            event_id="e2",
            state="APPROVED",
            timestamp=1001,
            source="test",
            details={},
            previous_hash="wrong_hash",
        )
    assert "Hash chain break" in str(exc_info.value)
