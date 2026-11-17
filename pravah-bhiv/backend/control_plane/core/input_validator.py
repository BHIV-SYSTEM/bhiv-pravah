"""
Input Validation Hardening Module

Provides centralized, strict validation for all API inputs with:
- Type checking
- Range validation
- String length limits
- Enum constraints
- Array bounds
"""

import re
from typing import Any, Dict, List, Optional, Union


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class InputValidator:
    """Centralized input validation for production hardening."""

    # Configuration constraints
    MAX_APP_NAME_LENGTH = 100
    MAX_REASON_LENGTH = 500
    MAX_DURATION_MINUTES = 1440  # 24 hours
    MIN_DURATION_MINUTES = 1
    MAX_LIMIT_PARAM = 1000
    MIN_LIMIT_PARAM = 1
    MAX_LATENCY_MS = 60000  # 60 seconds
    MAX_ERRORS_LAST_MIN = 1000
    MAX_WORKERS = 10000

    VALID_STATES = {"running", "degraded", "crashed"}
    VALID_ENVIRONMENTS = {"dev", "staging", "prod"}
    VALID_APP_RUNTIME_TYPES = {"pod", "service", "function", "container"}
    VALID_OVERRIDE_ACTIONS = {"set_freeze", "clear_freeze", "freeze"}

    @classmethod
    def validate_app_name(cls, app_name: Optional[str]) -> str:
        """Validate app name format and length."""
        if not app_name:
            raise ValidationError("app_name is required and cannot be empty")

        app_name = app_name.strip()
        if not app_name:
            raise ValidationError("app_name cannot be whitespace-only")

        if len(app_name) > cls.MAX_APP_NAME_LENGTH:
            raise ValidationError(f"app_name exceeds max length of {cls.MAX_APP_NAME_LENGTH}")

        # Allow alphanumeric, hyphens, underscores, dots, and spaces
        if not re.match(r"^[a-zA-Z0-9._ -]+$", app_name):
            raise ValidationError("app_name contains invalid characters; use alphanumeric, dots, hyphens, underscores, spaces")

        return app_name

    @classmethod
    def validate_duration_minutes(cls, duration: Any) -> int:
        """Validate duration_minutes parameter."""
        try:
            duration_int = int(duration)
        except (TypeError, ValueError):
            raise ValidationError(f"duration_minutes must be an integer, got {type(duration).__name__}")

        if duration_int < cls.MIN_DURATION_MINUTES or duration_int > cls.MAX_DURATION_MINUTES:
            raise ValidationError(
                f"duration_minutes must be between {cls.MIN_DURATION_MINUTES} and {cls.MAX_DURATION_MINUTES}"
            )

        return duration_int

    @classmethod
    def validate_reason(cls, reason: Optional[str]) -> str:
        """Validate override reason."""
        if not reason:
            return "manual_override"

        reason = str(reason).strip()
        if len(reason) > cls.MAX_REASON_LENGTH:
            raise ValidationError(f"reason exceeds max length of {cls.MAX_REASON_LENGTH}")

        # Allow printable ASCII and common UTF-8
        if not all(ord(c) >= 32 for c in reason):
            raise ValidationError("reason contains non-printable characters")

        return reason

    @classmethod
    def validate_action(cls, action: str) -> str:
        """Validate control-plane override action."""
        action = (action or "set_freeze").strip().lower()
        if action == "freeze":
            action = "set_freeze"

        if action not in cls.VALID_OVERRIDE_ACTIONS:
            raise ValidationError(f"action must be one of {cls.VALID_OVERRIDE_ACTIONS}")

        return action

    @classmethod
    def validate_limit_param(cls, limit: Any) -> int:
        """Validate history limit parameter."""
        try:
            limit_int = int(limit)
        except (TypeError, ValueError):
            raise ValidationError(f"limit must be an integer, got {type(limit).__name__}")

        if limit_int < cls.MIN_LIMIT_PARAM or limit_int > cls.MAX_LIMIT_PARAM:
            raise ValidationError(
                f"limit must be between {cls.MIN_LIMIT_PARAM} and {cls.MAX_LIMIT_PARAM}"
            )

        return limit_int

    @classmethod
    def validate_runtime_payload(cls, payload: Dict[str, Any]) -> None:
        """Validate runtime decision payload fields."""
        if not isinstance(payload, dict):
            raise ValidationError("Payload must be a JSON object")

        # Required fields
        required_fields = {"state", "env", "app", "latency_ms", "errors_last_min", "workers"}
        missing = required_fields - set(payload.keys())
        if missing:
            raise ValidationError(f"Missing required fields: {missing}")

        # Validate state
        state = payload.get("state")
        if state not in cls.VALID_STATES:
            raise ValidationError(f"state must be one of {cls.VALID_STATES}, got {state}")

        # Validate environment
        env = payload.get("env")
        if env not in cls.VALID_ENVIRONMENTS:
            raise ValidationError(f"env must be one of {cls.VALID_ENVIRONMENTS}, got {env}")

        # Validate app_id (same constraints as app_name)
        try:
            cls.validate_app_name(payload.get("app"))
        except ValidationError as e:
            raise ValidationError(f"Invalid app field: {str(e)}")

        # Validate metrics
        try:
            latency = int(payload.get("latency_ms", 0))
            if latency < 0 or latency > cls.MAX_LATENCY_MS:
                raise ValidationError(
                    f"latency_ms must be between 0 and {cls.MAX_LATENCY_MS}, got {latency}"
                )
        except (TypeError, ValueError):
            raise ValidationError("latency_ms must be a non-negative integer")

        try:
            errors = int(payload.get("errors_last_min", 0))
            if errors < 0 or errors > cls.MAX_ERRORS_LAST_MIN:
                raise ValidationError(
                    f"errors_last_min must be between 0 and {cls.MAX_ERRORS_LAST_MIN}, got {errors}"
                )
        except (TypeError, ValueError):
            raise ValidationError("errors_last_min must be a non-negative integer")

        try:
            workers = int(payload.get("workers", 1))
            if workers < 1 or workers > cls.MAX_WORKERS:
                raise ValidationError(
                    f"workers must be between 1 and {cls.MAX_WORKERS}, got {workers}"
                )
        except (TypeError, ValueError):
            raise ValidationError("workers must be a positive integer")

    @classmethod
    def validate_control_plane_override_payload(cls, payload: Dict[str, Any]) -> tuple:
        """Validate control-plane override POST payload."""
        if not isinstance(payload, dict):
            raise ValidationError("Payload must be a JSON object")

        app_name = cls.validate_app_name(payload.get("app_name"))
        action = cls.validate_action(payload.get("action"))

        # Support duration in seconds ("duration") or duration in minutes ("duration_minutes")
        duration_val = payload.get("duration_minutes")
        if duration_val is None and "duration" in payload:
            try:
                duration_val = max(1, int(payload["duration"]) // 60)
            except (TypeError, ValueError):
                duration_val = None
        duration = cls.validate_duration_minutes(duration_val if duration_val is not None else 30)
        reason = cls.validate_reason(payload.get("reason"))

        return app_name, action, duration, reason
