from typing import Any, Dict


REQUIRED_FIELDS = ("service_id", "action", "trace_id")


def validate_execution_gate(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate minimal execution payload before calling the executor.

    Returns a normalized allow/block response so callers can uniformly handle
    validation outcomes.
    """
    if not isinstance(payload, dict):
        return {"allow": False, "reason": "payload_must_be_object"}

    missing = [field for field in REQUIRED_FIELDS if not payload.get(field)]
    if missing:
        return {
            "allow": False,
            "reason": "missing_required_fields",
            "missing": missing,
        }

    return {"allow": True, "reason": "ok"}
