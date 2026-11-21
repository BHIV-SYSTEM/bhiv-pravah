"""
Tests for Schema Validation Layer (v1.0)
Validates strict schema enforcement, inbound and outbound payloads, structured errors.
"""

import pytest
from pravah.schema_validator import (
    InboundSignalV1,
    OutboundEventV1,
    SchemaValidatorV1,
    SchemaValidationError,
    ValidationErrorCode,
)


def test_valid_inbound_signal():
    payload = {
        "schema_version": "1.0",
        "trace_id": "tr-001",
        "execution_id": "exec-100",
        "timestamp": "2026-11-17T12:00:00Z",
        "source": "governance_agent",
        "signal_type": "execution",
        "payload": {"action": "scale_up", "target": "worker-1"},
    }
    result = SchemaValidatorV1.validate_inbound_signal(payload)
    assert result.valid is True
    assert result.schema_version == "1.0"
    assert len(result.errors) == 0
    assert result.validated_payload["trace_id"] == "tr-001"


def test_reject_unsupported_schema_version():
    for bad_ver in ["0.9", "2.0", "1.1", "v1.0"]:
        payload = {
            "schema_version": bad_ver,
            "trace_id": "tr-001",
            "execution_id": "exec-100",
            "timestamp": "2026-11-17T12:00:00Z",
            "source": "governance_agent",
            "signal_type": "execution",
            "payload": {"action": "scale_up"},
        }
        result = SchemaValidatorV1.validate_inbound_signal(payload)
        assert result.valid is False
        assert result.errors[0].error_code == ValidationErrorCode.UNSUPPORTED_SCHEMA_VERSION


def test_reject_missing_schema_version():
    payload = {
        "trace_id": "tr-001",
        "execution_id": "exec-100",
        "timestamp": "2026-11-17T12:00:00Z",
        "source": "governance_agent",
        "signal_type": "execution",
        "payload": {"action": "scale_up"},
    }
    result = SchemaValidatorV1.validate_inbound_signal(payload)
    assert result.valid is False
    assert result.errors[0].error_code == ValidationErrorCode.MISSING_REQUIRED_FIELD


def test_reject_missing_required_fields():
    required_fields = ["trace_id", "execution_id", "timestamp", "source", "signal_type", "payload"]
    base = {
        "schema_version": "1.0",
        "trace_id": "tr-001",
        "execution_id": "exec-100",
        "timestamp": "2026-11-17T12:00:00Z",
        "source": "governance_agent",
        "signal_type": "execution",
        "payload": {"action": "scale_up"},
    }
    for field in required_fields:
        bad = dict(base)
        del bad[field]
        result = SchemaValidatorV1.validate_inbound_signal(bad)
        assert result.valid is False
        assert any(e.error_code == ValidationErrorCode.MISSING_REQUIRED_FIELD for e in result.errors)


def test_reject_empty_strings():
    for field in ["trace_id", "execution_id", "source", "signal_type"]:
        bad = {
            "schema_version": "1.0",
            "trace_id": "tr-001",
            "execution_id": "exec-100",
            "timestamp": "2026-11-17T12:00:00Z",
            "source": "governance_agent",
            "signal_type": "execution",
            "payload": {"action": "scale_up"},
        }
        bad[field] = "   "  # whitespace
        result = SchemaValidatorV1.validate_inbound_signal(bad)
        assert result.valid is False


def test_reject_invalid_timestamp():
    bad = {
        "schema_version": "1.0",
        "trace_id": "tr-001",
        "execution_id": "exec-100",
        "timestamp": "not-a-valid-date-time",
        "source": "governance_agent",
        "signal_type": "execution",
        "payload": {"action": "scale_up"},
    }
    result = SchemaValidatorV1.validate_inbound_signal(bad)
    assert result.valid is False
    assert any(e.error_code == ValidationErrorCode.INVALID_TIMESTAMP for e in result.errors)


def test_reject_non_dict_payload():
    bad = {
        "schema_version": "1.0",
        "trace_id": "tr-001",
        "execution_id": "exec-100",
        "timestamp": "2026-11-17T12:00:00Z",
        "source": "governance_agent",
        "signal_type": "execution",
        "payload": "string-payload-not-dict",
    }
    result = SchemaValidatorV1.validate_inbound_signal(bad)
    assert result.valid is False


def test_enforce_inbound_raises_schema_validation_error():
    with pytest.raises(SchemaValidationError) as exc_info:
        SchemaValidatorV1.enforce_inbound({"schema_version": "0.9"})
    assert exc_info.value.validation_result.valid is False
    assert "Schema v1.0 validation failed" in str(exc_info.value)


def test_valid_outbound_event():
    valid_hash = "a" * 64
    valid_outbound = {
        "schema_version": "1.0",
        "trace_id": "tr-001",
        "execution_id": "exec-100",
        "event_id": "evt-1",
        "sequence": 1,
        "state": "APPROVED",
        "event_hash": valid_hash,
        "previous_hash": "",
        "state_hash": valid_hash,
        "timestamp": "2026-11-17T12:00:00Z",
        "source": "stream_processor",
        "details": {"action": "approved"},
        "sequence_hash": valid_hash,
        "lineage_proof": valid_hash,
    }
    result = SchemaValidatorV1.validate_outbound_event(valid_outbound)
    assert result.valid is True


def test_reject_outbound_event_invalid_hash_or_sequence():
    valid_hash = "a" * 64
    base = {
        "schema_version": "1.0",
        "trace_id": "tr-001",
        "execution_id": "exec-100",
        "event_id": "evt-1",
        "sequence": 0,  # Invalid: sequence must be >= 1
        "state": "APPROVED",
        "event_hash": "short_hash",  # Invalid: not 64 chars
        "previous_hash": "",
        "state_hash": valid_hash,
        "timestamp": 12345678,
        "source": "stream_processor",
        "details": {},
        "sequence_hash": valid_hash,
        "lineage_proof": valid_hash,
    }
    result = SchemaValidatorV1.validate_outbound_event(base)
    assert result.valid is False
