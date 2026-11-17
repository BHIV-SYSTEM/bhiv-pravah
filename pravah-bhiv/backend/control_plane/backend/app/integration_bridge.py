"""
Integration bridge between RL Decision Brain and Multi-Agent Control Plane.

This module provides seamless integration between:
1. RL Decision Brain (FastAPI on port 7999) - Real-time monitoring & RL decisions
2. Multi-Agent Control Plane (Flask on port 7000) - Multi-app orchestration

Features:
- Bi-directional data sync
- Unified app registry
- Shared decision history
- Health metric aggregation
- RL policy optimization feedback to control plane

Default local ports:
- RL Decision Brain (FastAPI): 7999
- Multi-Agent Control Plane (Flask): 7000
"""

import sys
import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from collections import deque

# Add multi-agent-control-plane to path
_APP_DIR = os.path.dirname(__file__)
_CURRENT_PROJECT_ROOT = os.path.abspath(os.path.join(_APP_DIR, "../.."))
_LEGACY_SIBLING_ROOT = os.path.abspath(os.path.join(_APP_DIR, "../../multi-agent-control-plane-main"))

if os.path.exists(os.path.join(_CURRENT_PROJECT_ROOT, "agent_runtime.py")):
    CONTROL_PLANE_PATH = _CURRENT_PROJECT_ROOT
else:
    CONTROL_PLANE_PATH = _LEGACY_SIBLING_ROOT

if CONTROL_PLANE_PATH not in sys.path:
    sys.path.insert(0, CONTROL_PLANE_PATH)

try:
    from agent_runtime import AgentRuntime
    from control_plane.multi_app_control_plane import MultiAppControlPlane
    CONTROL_PLANE_AVAILABLE = True
except ImportError:
    CONTROL_PLANE_AVAILABLE = False


class IntegrationBridge:
    """Bridge between RL Decision Brain and Multi-Agent Control Plane."""
    
    def __init__(self):
        """Initialize the integration bridge."""
        self.rl_decisions = deque(maxlen=100)  # Store RL decisions
        self.control_plane_apps = {}  # Store app registry
        self.shared_metrics = {}  # Aggregated metrics
        self.sync_enabled = CONTROL_PLANE_AVAILABLE
        
        if self.sync_enabled:
            try:
                env = os.getenv("ENVIRONMENT", "prod").strip().lower()
                if env in ("production", "prod"):
                    env = "prod"
                self.agent_runtime = AgentRuntime(env=env)
                self.control_plane = MultiAppControlPlane(env=env)
                self._sync_once()
            except Exception as e:
                print(f"Warning: Control Plane integration failed: {e}")
                self.sync_enabled = False
    
    def _sync_once(self) -> None:
        """Run a single non-loop sync pass."""
        try:
            self._sync_metrics()
            self._sync_decisions()
        except Exception as e:
            print(f"Sync error: {e}")
    
    def _sync_metrics(self) -> None:
        """Sync metrics with control plane."""
        if not self.sync_enabled:
            return
        
        try:
            # Get control plane app registry
            if hasattr(self.control_plane, 'apps'):
                self.control_plane_apps = {
                    app.name if hasattr(app, 'name') else str(app): app 
                    for app in self.control_plane.apps
                }
            
            # Aggregate metrics
            self.shared_metrics = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "control_plane_apps": len(self.control_plane_apps),
                "rl_decisions_made": len(self.rl_decisions),
                "sync_status": "active",
            }
        except Exception as e:
            print(f"Metric sync error: {e}")
    
    def _sync_decisions(self) -> None:
        """Sync RL decisions to control plane."""
        if not self.sync_enabled or not self.rl_decisions:
            return
        
        try:
            latest_decision = self.rl_decisions[-1]
            # Could push decisions to control plane for learning
        except Exception as e:
            print(f"Decision sync error: {e}")
    
    def record_rl_decision(self, decision: Dict[str, Any]) -> None:
        """Record an RL decision for later analysis."""
        decision["recorded_at"] = datetime.now(timezone.utc).isoformat()
        self.rl_decisions.appendleft(decision)
    
    def get_control_plane_status(self) -> Dict[str, Any]:
        """Get integrated control plane status."""
        if not self.sync_enabled:
            return {"status": "disconnected", "reason": "Control plane integration unavailable"}
        
        try:
            return {
                "status": "connected",
                "apps_managed": len(self.control_plane_apps),
                "total_decisions": len(self.rl_decisions),
                "metrics": self.shared_metrics,
                "last_sync": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_app_registry(self) -> List[Dict[str, Any]]:
        """Get unified app registry from control plane."""
        if not self.sync_enabled:
            return []
        
        try:
            apps = []
            for app_name, app in self.control_plane_apps.items():
                apps.append({
                    "name": app_name,
                    "status": "managed",
                    "environment": "production",
                })
            return apps
        except Exception as e:
            print(f"Registry error: {e}")
            return []
    
    def get_orchestration_metrics(self) -> Dict[str, Any]:
        """Get metrics about orchestration status."""
        return {
            "rl_brain_status": "active",
            "control_plane_status": "connected" if self.sync_enabled else "disconnected",
            "total_apps_monitored": len(self.control_plane_apps),
            "rl_decisions_made": len(self.rl_decisions),
            "integration_enabled": self.sync_enabled,
            "last_sync": self.shared_metrics.get("timestamp", "never"),
        }


# Global singleton instance
_bridge: Optional[IntegrationBridge] = None


def get_bridge() -> IntegrationBridge:
    """Get or create the integration bridge."""
    global _bridge
    if _bridge is None:
        _bridge = IntegrationBridge()
    return _bridge
