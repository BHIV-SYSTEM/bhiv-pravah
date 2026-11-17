# core/runtime_event_validator.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import json


ALLOWED_EVENT_TYPES = {"deploy", "scale", "restart", "crash", "overload", "false_alarm", "critical_system_failure", "high_cpu", "high_memory", "low_load"}

# These keys MUST exist. We validate only; we never modify the incoming payload.
REQUIRED_KEYS = {"event_id", "event_type", "timestamp"}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    payload: Optional[Dict[str, Any]]
    error: Optional[str]


def _safe_json_dumps(obj: Any) -> str:
    """Safe JSON serialization for logs without throwing."""
    try:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(obj)


def validate_runtime_event(event_data: Dict[str, Any]) -> ValidationResult:
    """
    Validate runtime event schema without mutating the payload.

    ✅ Task-1 compliance:
    - Runtime → RL payload must be passed unchanged.
    - Do NOT reshape fields beyond what RL already accepts.
    - If invalid, refuse to send to RL (fail-fast, not silent).
    """

    if not isinstance(event_data, dict):
        return ValidationResult(False, None, "event_data must be a dict")

    # Missing required keys -> invalid (DO NOT AUTO-FIX).
    missing = REQUIRED_KEYS - set(event_data.keys())
    if missing:
        return ValidationResult(
            False,
            None,
            f"missing required keys: {sorted(list(missing))}"
        )

    # Validate event_type
    event_type = event_data.get("event_type")
    if event_type not in ALLOWED_EVENT_TYPES:
        return ValidationResult(
            False,
            None,
            f"invalid event_type: {event_type!r} (allowed: {sorted(list(ALLOWED_EVENT_TYPES))})"
        )

    # Basic type checks (still no mutation)
    if not isinstance(event_data.get("event_id"), (str, int)):
        return ValidationResult(False, None, "event_id must be str or int")

    # timestamp may be str/int/float depending on implementation
    if not isinstance(event_data.get("timestamp"), (str, int, float)):
        return ValidationResult(False, None, "timestamp must be str/int/float")

    # ✅ Valid. Return the SAME object reference (unchanged).
    return ValidationResult(True, event_data, None)


# Backwards-compatible signature if your pipeline currently uses (ok, payload, err)
def validate_event(event_data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Compatibility wrapper:
    returns (ok, payload, error)
    """
    res = validate_runtime_event(event_data)
    return res.ok, res.payload, res.error

def validate_and_log_payload(event_data: Dict[str, Any], stage: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate payload and log for integrity tracking.
    Returns (is_valid, validated_payload, error_msg)
    """
    res = validate_runtime_event(event_data)
    
    # Log payload integrity
    if res.ok:
        payload_json = _safe_json_dumps(res.payload)
        with open('payload_integrity.log', 'a') as f:
            f.write(f"{stage}: {payload_json}\n")
    
    return res.ok, res.payload, res.error

class RuntimeEventValidator:
    """Runtime event validation utilities."""
    
    @staticmethod
    def log_payload_integrity(payload: Dict[str, Any], stage: str):
        """Log payload for integrity verification."""
        payload_json = _safe_json_dumps(payload)
        with open('payload_integrity.log', 'a') as f:
            f.write(f"{stage}: {payload_json}\n")