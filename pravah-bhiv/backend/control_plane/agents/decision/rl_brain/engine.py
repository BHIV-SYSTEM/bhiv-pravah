"""
RL Decision Brain - Production-Hardened Demo-Frozen Agent
Stateless | Deterministic | Safety-Caged
"""

from typing import Dict, Any, Optional
from enum import Enum
import time

class Environment(Enum):
    DEV = "dev"
    STAGE = "stage"
    PROD = "prod"

class Action(Enum):
    NOOP = "noop"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    RESTART = "restart"

class RLDecisionBrain:
    """
    Demo-frozen RL agent with hard safety guarantees
    - Stateless: No persistence between requests
    - Deterministic: Identical input → identical output
    - Safety-caged: Environment-scoped action filtering
    """
    
    # Environment action scope (LOCKED)
    ACTION_SCOPE = {
        Environment.DEV: {Action.NOOP, Action.SCALE_UP, Action.SCALE_DOWN, Action.RESTART},
        Environment.STAGE: {Action.NOOP, Action.SCALE_UP, Action.SCALE_DOWN},
        Environment.PROD: {Action.NOOP, Action.RESTART}
    }
    
    # Frozen decision logic (LOCKED)
    DECISION_MAP = {
        ("dev", "high_cpu"): Action.SCALE_UP,
        ("dev", "high_memory"): Action.SCALE_UP,
        ("dev", "crash"): Action.RESTART,
        ("dev", "low_load"): Action.SCALE_DOWN,
        ("stage", "high_cpu"): Action.SCALE_UP,
        ("stage", "high_memory"): Action.SCALE_UP,
        ("stage", "crash"): Action.NOOP,
        ("stage", "low_load"): Action.SCALE_DOWN,
        ("prod", "high_cpu"): Action.NOOP,
        ("prod", "high_memory"): Action.NOOP,
        ("prod", "crash"): Action.RESTART,
        ("prod", "low_load"): Action.NOOP,
    }
    
    def decide(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make stateless decision based on request
        
        Input schema (LOCKED):
        {
            "environment": "dev" | "stage" | "prod",
            "event_type": str,
            "metrics": {
                "cpu_percent": float,
                "memory_percent": float,
                "error_rate": float
            }
        }
        
        Output schema (LOCKED):
        {
            "action": str,
            "reason": str,
            "demo_frozen": true,
            "timestamp": float,
            "environment": str,
            "safety_filtered": bool
        }
        """
        # Validate input
        validation_error = self._validate_request(request)
        if validation_error:
            return self._noop_response(validation_error, request.get("environment", "unknown"))
        
        env_str = request["environment"].lower()
        event_type = request["event_type"].lower()
        
        # Parse environment
        try:
            environment = Environment(env_str)
        except ValueError:
            return self._noop_response(f"Invalid environment: {env_str}", env_str)
        
        # Get proposed action from frozen decision map
        decision_key = (env_str, event_type)
        proposed_action = self.DECISION_MAP.get(decision_key, Action.NOOP)
        
        # Safety filter: enforce action scope
        allowed_actions = self.ACTION_SCOPE[environment]
        if proposed_action not in allowed_actions:
            return {
                "action": Action.NOOP.value,
                "reason": f"Action {proposed_action.value} not allowed in {env_str}, downgraded to NOOP",
                "demo_frozen": True,
                "timestamp": time.time(),
                "environment": env_str,
                "safety_filtered": True,
                "proposed_action": proposed_action.value
            }
        
        # Emit safe action
        return {
            "action": proposed_action.value,
            "reason": f"Deterministic decision for {event_type} in {env_str}",
            "demo_frozen": True,
            "timestamp": time.time(),
            "environment": env_str,
            "safety_filtered": False
        }
    
    def _validate_request(self, request: Dict[str, Any]) -> Optional[str]:
        """Validate request schema"""
        if not isinstance(request, dict):
            return "Request must be a JSON object"
        
        if "environment" not in request:
            return "Missing required field: environment"
        
        if "event_type" not in request:
            return "Missing required field: event_type"
        
        # Note: 'metrics' validation relaxed slightly to allow calls without it if not needed,
        # but adhering to original logic which checked for it.
        if "metrics" not in request:
            return "Missing required field: metrics"
        
        metrics = request["metrics"]
        if not isinstance(metrics, dict):
            return "Field 'metrics' must be an object"
        
        return None
    
    def _noop_response(self, reason: str, environment: str) -> Dict[str, Any]:
        """Generate NOOP response with reason"""
        return {
            "action": Action.NOOP.value,
            "reason": reason,
            "demo_frozen": True,
            "timestamp": time.time(),
            "environment": environment,
            "safety_filtered": False
        }

    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        return {
            "status": "healthy",
            "demo_frozen": True,
            "learning_enabled": False,
            "exploration_enabled": False,
            "stateless": True
        }
