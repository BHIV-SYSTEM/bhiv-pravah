"""Deterministic, explainable decision engine for RL-style policy decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

try:
    from .config import ACTION_SCOPE, CPU_SCALE_DOWN_THRESHOLD, CPU_SCALE_UP_THRESHOLD, MEMORY_SCALE_UP_THRESHOLD
    from .schemas import DecisionRequest, DecisionResponse
except ImportError:
    from config import ACTION_SCOPE, CPU_SCALE_DOWN_THRESHOLD, CPU_SCALE_UP_THRESHOLD, MEMORY_SCALE_UP_THRESHOLD
    from schemas import DecisionRequest, DecisionResponse


class DecisionEngine:
    """Pure decision helper with no external side effects."""

    @staticmethod
    def decide(request: DecisionRequest) -> DecisionResponse:
        """Produce a unique decision from validated input metrics."""

        selected_action = "noop"
        reason = "No threshold exceeded"
        confidence = 0.95

        if request.cpu >= 90:
            selected_action = "scale_up"
            reason = "CPU above threshold"
            confidence = 0.91
        elif request.cpu < CPU_SCALE_DOWN_THRESHOLD:
            selected_action = "scale_down"
            reason = "CPU below threshold"
            confidence = 0.89
        elif request.memory > MEMORY_SCALE_UP_THRESHOLD:
            selected_action = "scale_up"
            reason = "Memory above threshold"
            confidence = 0.9

        allowed_actions = ACTION_SCOPE[request.environment.value]
        if selected_action not in allowed_actions:
            selected_action = "noop"
            if request.environment.value == "PROD":
                reason = "Action constrained by PROD environment"
            else:
                reason = "Action constrained by environment"
            confidence = 0.99

        decision_id = uuid4()

        return DecisionResponse(
            decision_id=decision_id,
            environment=request.environment,
            selected_action=selected_action,
            reason=reason,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            version="v1",
        )
