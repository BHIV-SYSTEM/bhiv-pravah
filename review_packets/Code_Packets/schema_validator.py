"""
PRAVAH Schema Validation Layer (v1.0)
Strict schema interfaces enforcing Schema Version 1.0 for Stream Processing and Replay.

Guarantees:
- Schema v1.0 strict enforcement
- Strict type and required field checking
- Inbound signal validation
- Outbound event validation
- Structured error reporting with actionable error codes
- Backward compatibility with legacy schema fields
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class ValidationErrorCode(str, Enum):
    UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_DATA_TYPE = "INVALID_DATA_TYPE"
    MALFORMED_PAYLOAD = "MALFORMED_PAYLOAD"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class ValidationErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    message: str
    error_code: ValidationErrorCode
    input_value: Optional[Any] = None


class ValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    schema_version: str
    errors: List[ValidationErrorDetail] = Field(default_factory=list)
    validated_payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "schema_version": self.schema_version,
            "errors": [e.model_dump() for e in self.errors],
            "validated_payload": self.validated_payload,
        }


class SchemaValidationError(Exception):
    """Raised when payload fails Schema v1.0 validation."""

    def __init__(self, validation_result: ValidationResult):
        self.validation_result = validation_result
        err_msgs = [f"{e.field}: {e.message} ({e.error_code.value})" for e in validation_result.errors]
        super().__init__(f"Schema v1.0 validation failed: {'; '.join(err_msgs)}")


def _validate_iso_timestamp(ts: Any) -> str:
    if not isinstance(ts, (str, int, float, datetime.datetime)):
        raise ValueError(f"Timestamp must be ISO-8601 string, integer epoch, or datetime object, got {type(ts).__name__}")
    if isinstance(ts, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
        except Exception as e:
            raise ValueError(f"Invalid numeric timestamp {ts}: {e}")
    if isinstance(ts, datetime.datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
        return ts.isoformat()
    if isinstance(ts, str):
        # Allow trailing Z
        norm = ts.replace("Z", "+00:00")
        try:
            datetime.datetime.fromisoformat(norm)
            return ts
        except Exception:
            raise ValueError(f"Invalid ISO-8601 timestamp string: {ts}")
    raise ValueError("Invalid timestamp")


class InboundSignalV1(BaseModel):
    """Canonical Inbound Signal Model adhering strictly to Schema v1.0."""
    model_config = ConfigDict(frozen=True, extra="allow")

    schema_version: Literal["1.0"] = Field(..., description="Must be exactly '1.0'")
    trace_id: str = Field(..., min_length=1, description="Unique trace identifier")
    execution_id: str = Field(..., min_length=1, description="Execution run identifier")
    timestamp: str = Field(..., description="ISO-8601 timestamp string")
    source: str = Field(..., min_length=1, description="Originating service or agent")
    signal_type: str = Field(..., min_length=1, description="Signal type (e.g. execution, verification, telemetry)")
    payload: Dict[str, Any] = Field(..., description="Event data dictionary")

    # Optional legacy fields for backward compatibility with signal_schema.json
    service_id: Optional[str] = None
    action: Optional[str] = None
    status: Optional[str] = None
    type: Optional[str] = None

    @field_validator("timestamp")
    @classmethod
    def check_timestamp(cls, v: Any) -> str:
        return _validate_iso_timestamp(v)

    @field_validator("trace_id", "execution_id", "source", "signal_type")
    @classmethod
    def check_non_empty_str(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()

    @field_validator("payload")
    @classmethod
    def check_payload(cls, v: Any) -> Dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("Payload must be a dictionary")
        return v


class OutboundEventV1(BaseModel):
    """Canonical Outbound Replay Event Model adhering strictly to Schema v1.0."""
    model_config = ConfigDict(frozen=True, extra="allow")

    schema_version: Literal["1.0"] = Field(..., description="Must be exactly '1.0'")
    trace_id: str = Field(..., min_length=1)
    execution_id: str = Field(..., min_length=1)
    event_id: str = Field(..., min_length=1)
    sequence: int = Field(..., ge=1, description="Monotonic sequence number starting from 1")
    state: Literal["CREATED", "APPROVED", "EXECUTED", "COMPLETED", "FAILED"] = Field(...)
    event_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 hash of event")
    previous_hash: str = Field(default="", description="SHA-256 hash of previous event or empty for genesis")
    state_hash: str = Field(..., min_length=64, max_length=64, description="Cumulative state fingerprint")
    timestamp: Union[int, str] = Field(..., description="Timestamp of recording")
    source: str = Field(..., min_length=1)
    details: Dict[str, Any] = Field(default_factory=dict)
    sequence_hash: str = Field(..., min_length=64, max_length=64)
    lineage_proof: str = Field(..., min_length=64, max_length=64)

    @field_validator("sequence")
    @classmethod
    def check_sequence(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Sequence must be >= 1")
        return v


class SchemaValidatorV1:
    """Unified Schema Validator for PRAVAH Stream Processing and Replay."""

    SCHEMA_VERSION = "1.0"

    @classmethod
    def validate_inbound_signal(cls, data: Any) -> ValidationResult:
        if not isinstance(data, dict):
            return ValidationResult(
                valid=False,
                schema_version=getattr(data, "schema_version", "unknown") if hasattr(data, "schema_version") else "unknown",
                errors=[
                    ValidationErrorDetail(
                        field="root",
                        message=f"Payload must be a JSON object (dict), got {type(data).__name__}",
                        error_code=ValidationErrorCode.MALFORMED_PAYLOAD,
                        input_value=str(data)[:100],
                    )
                ],
            )

        # Explicit schema_version check
        ver = data.get("schema_version")
        if ver is None:
            return ValidationResult(
                valid=False,
                schema_version="missing",
                errors=[
                    ValidationErrorDetail(
                        field="schema_version",
                        message="Missing required field 'schema_version'. Expected '1.0'",
                        error_code=ValidationErrorCode.MISSING_REQUIRED_FIELD,
                        input_value=None,
                    )
                ],
            )
        if ver != cls.SCHEMA_VERSION:
            return ValidationResult(
                valid=False,
                schema_version=str(ver),
                errors=[
                    ValidationErrorDetail(
                        field="schema_version",
                        message=f"Unsupported schema version: '{ver}'. Only '1.0' is supported",
                        error_code=ValidationErrorCode.UNSUPPORTED_SCHEMA_VERSION,
                        input_value=ver,
                    )
                ],
            )

        try:
            model = InboundSignalV1(**data)
            return ValidationResult(
                valid=True,
                schema_version=cls.SCHEMA_VERSION,
                validated_payload=model.model_dump(),
            )
        except ValidationError as e:
            errors: List[ValidationErrorDetail] = []
            for err in e.errors():
                loc = ".".join(str(p) for p in err["loc"])
                err_type = err["type"]
                msg = err["msg"]

                if "missing" in err_type:
                    code = ValidationErrorCode.MISSING_REQUIRED_FIELD
                elif "timestamp" in loc or "timestamp" in msg:
                    code = ValidationErrorCode.INVALID_TIMESTAMP
                elif "type" in err_type:
                    code = ValidationErrorCode.INVALID_DATA_TYPE
                else:
                    code = ValidationErrorCode.MALFORMED_PAYLOAD

                errors.append(
                    ValidationErrorDetail(
                        field=loc,
                        message=msg,
                        error_code=code,
                        input_value=err.get("input"),
                    )
                )

            return ValidationResult(
                valid=False,
                schema_version=cls.SCHEMA_VERSION,
                errors=errors,
            )

    @classmethod
    def validate_outbound_event(cls, data: Any) -> ValidationResult:
        if not isinstance(data, dict):
            return ValidationResult(
                valid=False,
                schema_version="unknown",
                errors=[
                    ValidationErrorDetail(
                        field="root",
                        message=f"Outbound event must be a JSON object (dict), got {type(data).__name__}",
                        error_code=ValidationErrorCode.MALFORMED_PAYLOAD,
                        input_value=str(data)[:100],
                    )
                ],
            )

        ver = data.get("schema_version")
        if ver != cls.SCHEMA_VERSION:
            return ValidationResult(
                valid=False,
                schema_version=str(ver) if ver else "missing",
                errors=[
                    ValidationErrorDetail(
                        field="schema_version",
                        message=f"Unsupported schema version '{ver}'. Expected '1.0'",
                        error_code=ValidationErrorCode.UNSUPPORTED_SCHEMA_VERSION,
                        input_value=ver,
                    )
                ],
            )

        try:
            model = OutboundEventV1(**data)
            return ValidationResult(
                valid=True,
                schema_version=cls.SCHEMA_VERSION,
                validated_payload=model.model_dump(),
            )
        except ValidationError as e:
            errors: List[ValidationErrorDetail] = []
            for err in e.errors():
                loc = ".".join(str(p) for p in err["loc"])
                err_type = err["type"]
                msg = err["msg"]
                code = ValidationErrorCode.MISSING_REQUIRED_FIELD if "missing" in err_type else ValidationErrorCode.INVALID_DATA_TYPE
                errors.append(
                    ValidationErrorDetail(
                        field=loc,
                        message=msg,
                        error_code=code,
                        input_value=err.get("input"),
                    )
                )

            return ValidationResult(
                valid=False,
                schema_version=cls.SCHEMA_VERSION,
                errors=errors,
            )

    @classmethod
    def enforce_inbound(cls, data: Any) -> Dict[str, Any]:
        """Validate inbound signal and return normalized payload or raise SchemaValidationError."""
        res = cls.validate_inbound_signal(data)
        if not res.valid:
            raise SchemaValidationError(res)
        return res.validated_payload or {}

    @classmethod
    def enforce_outbound(cls, data: Any) -> Dict[str, Any]:
        """Validate outbound event and return normalized payload or raise SchemaValidationError."""
        res = cls.validate_outbound_event(data)
        if not res.valid:
            raise SchemaValidationError(res)
        return res.validated_payload or {}
