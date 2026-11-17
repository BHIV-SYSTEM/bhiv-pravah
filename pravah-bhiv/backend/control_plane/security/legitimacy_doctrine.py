# ==============================================================================
# AUTHORITY ARCHITECTURE NOTICE:
# LegitimacyDoctrine is a runtime evaluator ONLY.
# It evaluates constitutional rules defined by the policy/governance layer.
# It does not define legitimacy semantics. Legitimacy semantics remain owned
# by the constitutional policy layer outside of runtime sovereignty.
# ==============================================================================

from enum import Enum
from typing import Dict, Any, Optional

class LegitimacyStatus(Enum):
    ILLEGITIMATE = "ILLEGITIMATE"
    LEGITIMATE_AMBIGUOUS = "LEGITIMATE_AMBIGUOUS"
    LEGITIMATE_DEGRADED = "LEGITIMATE_DEGRADED"
    LEGITIMATE_VALID = "LEGITIMATE_VALID"

class LegitimacyRuntimeState(Enum):
    BLOCKED = "BLOCKED"
    HALTED = "HALTED"
    DEGRADED = "DEGRADED"
    ACTIVE = "ACTIVE"

class LegitimacyAction(Enum):
    REJECT = "REJECT"
    HALT = "HALT"
    REPLAY_ONLY = "REPLAY_ONLY"
    DEGRADED_ALLOWED = "DEGRADED_ALLOWED"
    EXECUTE = "EXECUTE"

class DependencyCondition(Enum):
    ALL_AVAILABLE = "ALL_AVAILABLE"
    PARTIAL_REPLAY_GAP = "PARTIAL_REPLAY_GAP"
    MISSING_DB_INDEX = "MISSING_DB_INDEX"
    RL_UNAVAILABLE = "RL_UNAVAILABLE"

class DependencyHealthProvider:
    """Provides status checks for key runtime dependencies (Redis, RL Decision Brain)."""

    def __init__(self, redis_bus: Optional[Any] = None, rl_client: Optional[Any] = None):
        self.redis_bus = redis_bus
        self.rl_client = rl_client

    def get_health_status(self) -> DependencyCondition:
        # Check if Redis and RL are available.
        # If any is degraded/unavailable, return DependencyCondition.RL_UNAVAILABLE
        # Otherwise, return DependencyCondition.ALL_AVAILABLE
        redis_ok = True
        if self.redis_bus is not None:
            redis_client = getattr(self.redis_bus, "redis_client", None)
            if redis_client is None:
                redis_ok = False
            else:
                try:
                    redis_client.ping()
                except Exception:
                    redis_ok = False
        else:
            redis_ok = False

        rl_ok = True
        if self.rl_client is not None:
            consec = getattr(self.rl_client, "_consecutive_failures", 0)
            mx = getattr(self.rl_client, "_max_failures", 3)
            if consec >= mx:
                rl_ok = False
            else:
                try:
                    health = self.rl_client.get_health()
                    if health.get("status") != "ok":
                        rl_ok = False
                except Exception:
                    rl_ok = False
        else:
            rl_ok = False

        if not redis_ok or not rl_ok:
            return DependencyCondition.RL_UNAVAILABLE
        return DependencyCondition.ALL_AVAILABLE

class LegitimacyDoctrine:
    @staticmethod
    def compute(sig_valid: bool, trace_valid: bool, schema_valid: bool, key_deps: DependencyCondition) -> tuple[str, str, str]:
        """
        Decision matrix from Section 6 of degraded_runtime_doctrine.md:
        Returns (legitimacy_state, runtime_state, action_allowed)
        """
        # Coerce key_deps to Enum if string is passed
        if isinstance(key_deps, str):
            try:
                key_deps = DependencyCondition[key_deps]
            except KeyError:
                key_deps = DependencyCondition.ALL_AVAILABLE

        if not sig_valid:
            return LegitimacyStatus.ILLEGITIMATE.value, LegitimacyRuntimeState.BLOCKED.value, LegitimacyAction.REJECT.value
        if not trace_valid:
            return LegitimacyStatus.ILLEGITIMATE.value, LegitimacyRuntimeState.BLOCKED.value, LegitimacyAction.HALT.value
        if not schema_valid:
            return LegitimacyStatus.ILLEGITIMATE.value, LegitimacyRuntimeState.BLOCKED.value, LegitimacyAction.REJECT.value
        if key_deps == DependencyCondition.MISSING_DB_INDEX:
            return LegitimacyStatus.LEGITIMATE_AMBIGUOUS.value, LegitimacyRuntimeState.HALTED.value, LegitimacyAction.HALT.value
        if key_deps == DependencyCondition.PARTIAL_REPLAY_GAP:
            return LegitimacyStatus.LEGITIMATE_AMBIGUOUS.value, LegitimacyRuntimeState.HALTED.value, LegitimacyAction.REPLAY_ONLY.value
        if key_deps == DependencyCondition.RL_UNAVAILABLE:
            return LegitimacyStatus.LEGITIMATE_DEGRADED.value, LegitimacyRuntimeState.DEGRADED.value, LegitimacyAction.DEGRADED_ALLOWED.value
        return LegitimacyStatus.LEGITIMATE_VALID.value, LegitimacyRuntimeState.ACTIVE.value, LegitimacyAction.EXECUTE.value
