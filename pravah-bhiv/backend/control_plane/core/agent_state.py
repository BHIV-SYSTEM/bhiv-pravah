#!/usr/bin/env python3
"""
Agent State Management
Manages the state machine for the autonomous agent runtime.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class AgentState(Enum):
    """Agent state enumeration following the sense-validate-decide-enforce-act-observe-explain loop."""
    IDLE = "idle"
    OBSERVING = "observing"  # sense
    VALIDATING = "validating"  # validate
    DECIDING = "deciding"  # decide
    ENFORCING = "enforcing"  # enforce
    ACTING = "acting"  # act
    OBSERVING_RESULTS = "observing_results"  # observe
    EXPLAINING = "explaining"  # explain
    BLOCKED = "blocked"  # error state
    SHUTTING_DOWN = "shutting_down"


class AgentStateManager:
    """Manages agent state transitions and history."""
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        AgentState.IDLE: {AgentState.OBSERVING, AgentState.SHUTTING_DOWN},
        AgentState.OBSERVING: {AgentState.VALIDATING, AgentState.IDLE, AgentState.BLOCKED},
        AgentState.VALIDATING: {AgentState.DECIDING, AgentState.IDLE, AgentState.BLOCKED},
        AgentState.DECIDING: {AgentState.ENFORCING, AgentState.BLOCKED},
        AgentState.ENFORCING: {AgentState.ACTING, AgentState.IDLE, AgentState.BLOCKED},
        AgentState.ACTING: {AgentState.OBSERVING_RESULTS, AgentState.BLOCKED},
        AgentState.OBSERVING_RESULTS: {AgentState.EXPLAINING, AgentState.BLOCKED},
        AgentState.EXPLAINING: {AgentState.IDLE, AgentState.BLOCKED},
        AgentState.BLOCKED: {AgentState.IDLE, AgentState.SHUTTING_DOWN},
        AgentState.SHUTTING_DOWN: set()  # terminal state
    }
    
    def __init__(self, agent_id: str, initial_state: AgentState = AgentState.IDLE):
        """Initialize state manager.
        
        Args:
            agent_id: Unique agent identifier
            initial_state: Starting state (default: IDLE)
        """
        self.agent_id = agent_id
        self._current_state = initial_state
        self._state_history: List[Dict[str, Any]] = []
        self._record_state_entry(initial_state, "initialization")
    
    @property
    def current_state(self) -> AgentState:
        """Get current state."""
        return self._current_state
    
    def can_transition_to(self, new_state: AgentState) -> bool:
        """Check if transition to new state is valid.
        
        Args:
            new_state: Target state
            
        Returns:
            True if transition is valid
        """
        return new_state in self.VALID_TRANSITIONS.get(self._current_state, set())
    
    def transition_to(self, new_state: AgentState, reason: str = "") -> bool:
        """Transition to a new state.
        
        Args:
            new_state: Target state
            reason: Reason for transition
            
        Returns:
            True if transition succeeded
            
        Raises:
            ValueError: If transition is invalid
        """
        if not self.can_transition_to(new_state):
            raise ValueError(
                f"Invalid state transition: {self._current_state.value} -> {new_state.value}"
            )
        
        old_state = self._current_state
        self._current_state = new_state
        self._record_state_entry(new_state, reason, from_state=old_state)
        return True
    
    def _record_state_entry(self, state: AgentState, reason: str, from_state: Optional[AgentState] = None):
        """Record state entry in history.
        
        Args:
            state: New state
            reason: Reason for entry
            from_state: Previous state (if transition)
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": self.agent_id,
            "state": state.value,
            "reason": reason
        }
        
        if from_state:
            entry["from_state"] = from_state.value
            entry["transition"] = f"{from_state.value} -> {state.value}"
        
        self._state_history.append(entry)
    
    def get_state_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get state history.
        
        Args:
            limit: Maximum number of entries to return (most recent first)
            
        Returns:
            List of state history entries
        """
        if limit:
            return self._state_history[-limit:]
        return self._state_history.copy()
    
    def get_current_state_info(self) -> Dict[str, Any]:
        """Get current state information.
        
        Returns:
            Dictionary with current state details
        """
        if not self._state_history:
            return {
                "agent_id": self.agent_id,
                "current_state": self._current_state.value,
                "entered_at": None,
                "duration_seconds": 0
            }
        
        last_entry = self._state_history[-1]
        entered_at = datetime.fromisoformat(last_entry["timestamp"])
        duration = (datetime.utcnow() - entered_at).total_seconds()
        
        return {
            "agent_id": self.agent_id,
            "current_state": self._current_state.value,
            "entered_at": last_entry["timestamp"],
            "duration_seconds": duration,
            "reason": last_entry.get("reason", "")
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state manager to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            "agent_id": self.agent_id,
            "current_state": self._current_state.value,
            "state_info": self.get_current_state_info(),
            "history_count": len(self._state_history)
        }
    
    def save_to_file(self, filepath: str):
        """Save state history to file.
        
        Args:
            filepath: Path to save file
        """
        data = {
            "agent_id": self.agent_id,
            "current_state": self._current_state.value,
            "history": self._state_history
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: str, agent_id: str) -> 'AgentStateManager':
        """Load state manager from file.
        
        Args:
            filepath: Path to load from
            agent_id: Agent ID for validation
            
        Returns:
            AgentStateManager instance
            
        Raises:
            ValueError: If agent_id doesn't match
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        if data["agent_id"] != agent_id:
            raise ValueError(f"Agent ID mismatch: expected {agent_id}, got {data['agent_id']}")
        
        manager = cls(agent_id, AgentState(data["current_state"]))
        manager._state_history = data["history"]
        
        return manager
