#!/usr/bin/env python3
"""
Agent Memory - Bounded Short-Term Memory
Implements bounded short-term memory for the autonomous agent with decision and app state tracking.
"""

from collections import deque
from datetime import datetime
from typing import Dict, Any, List, Optional, Deque
from dataclasses import dataclass, asdict
import json


@dataclass
class DecisionRecord:
    """Record of a single decision made by the agent."""
    timestamp: str
    decision_type: str
    decision_data: Dict[str, Any]
    outcome: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class AppStateSnapshot:
    """Snapshot of an application's state at a point in time."""
    timestamp: str
    app_id: str
    status: str  # running, stopped, error, deploying
    health: Dict[str, Any]
    recent_events: List[str]
    metrics: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class AgentMemory:
    """Bounded short-term memory for the autonomous agent.
    
    Implements FIFO eviction when memory bounds are exceeded.
    """
    
    def __init__(
        self,
        max_decisions: int = 50,
        max_states_per_app: int = 10,
        agent_id: Optional[str] = None
    ):
        """Initialize agent memory.
        
        Args:
            max_decisions: Maximum number of decisions to remember
            max_states_per_app: Maximum number of states per app to remember
            agent_id: Agent identifier for this memory
        """
        self.agent_id = agent_id
        self.max_decisions = max_decisions
        self.max_states_per_app = max_states_per_app
        
        # Decision memory (bounded deque)
        self.decision_memory: Deque[DecisionRecord] = deque(maxlen=max_decisions)
        
        # App state memory (dict of bounded deques)
        self.app_state_memory: Dict[str, Deque[AppStateSnapshot]] = {}
        
        # Memory statistics
        self.created_at = datetime.utcnow().isoformat()
        self.total_decisions_seen = 0
        self.total_states_seen = 0
    
    def remember_decision(
        self,
        decision_type: str,
        decision_data: Dict[str, Any],
        outcome: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> DecisionRecord:
        """Remember a decision made by the agent.
        
        Args:
            decision_type: Type of decision
            decision_data: Decision details
            outcome: Outcome of the decision (success/failure/pending)
            context: Context that led to the decision
            
        Returns:
            The created DecisionRecord
        """
        record = DecisionRecord(
            timestamp=datetime.utcnow().isoformat(),
            decision_type=decision_type,
            decision_data=decision_data,
            outcome=outcome,
            context=context
        )
        
        self.decision_memory.append(record)
        self.total_decisions_seen += 1
        
        return record
    
    def remember_app_state(
        self,
        app_id: str,
        status: str,
        health: Dict[str, Any],
        recent_events: List[str],
        metrics: Optional[Dict[str, Any]] = None
    ) -> AppStateSnapshot:
        """Remember an application's state.
        
        Args:
            app_id: Application identifier
            status: Current status
            health: Health metrics
            recent_events: Recent events for this app
            metrics: Additional metrics
            
        Returns:
            The created AppStateSnapshot
        """
        snapshot = AppStateSnapshot(
            timestamp=datetime.utcnow().isoformat(),
            app_id=app_id,
            status=status,
            health=health,
            recent_events=recent_events,
            metrics=metrics
        )
        
        # Create deque for this app if doesn't exist
        if app_id not in self.app_state_memory:
            self.app_state_memory[app_id] = deque(maxlen=self.max_states_per_app)
        
        self.app_state_memory[app_id].append(snapshot)
        self.total_states_seen += 1
        
        return snapshot
    
    def recall_recent_decisions(self, n: Optional[int] = None) -> List[DecisionRecord]:
        """Recall the N most recent decisions.
        
        Args:
            n: Number of decisions to recall (None = all)
            
        Returns:
            List of recent decisions (most recent last)
        """
        if n is None:
            return list(self.decision_memory)
        
        # Get last n decisions
        decisions = list(self.decision_memory)
        return decisions[-n:] if len(decisions) > n else decisions
    
    def recall_app_history(self, app_id: str, n: Optional[int] = None) -> List[AppStateSnapshot]:
        """Recall app state history.
        
        Args:
            app_id: Application identifier
            n: Number of states to recall (None = all)
            
        Returns:
            List of app state snapshots (most recent last)
        """
        if app_id not in self.app_state_memory:
            return []
        
        states = list(self.app_state_memory[app_id])
        
        if n is None:
            return states
        
        return states[-n:] if len(states) > n else states
    
    def get_last_decision(self) -> Optional[DecisionRecord]:
        """Get the most recent decision.
        
        Returns:
            Most recent decision or None
        """
        if self.decision_memory:
            return self.decision_memory[-1]
        return None
    
    def get_app_current_state(self, app_id: str) -> Optional[AppStateSnapshot]:
        """Get the current state of an app.
        
        Args:
            app_id: Application identifier
            
        Returns:
            Most recent app state or None
        """
        if app_id in self.app_state_memory and self.app_state_memory[app_id]:
            return self.app_state_memory[app_id][-1]
        return None
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics.
        
        Returns:
            Dictionary with memory stats
        """
        total_app_states = sum(len(states) for states in self.app_state_memory.values())
        
        return {
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "decision_count": len(self.decision_memory),
            "decision_capacity": self.max_decisions,
            "decision_utilization": f"{len(self.decision_memory) / self.max_decisions * 100:.1f}%",
            "app_count": len(self.app_state_memory),
            "total_app_states": total_app_states,
            "max_states_per_app": self.max_states_per_app,
            "total_decisions_seen": self.total_decisions_seen,
            "total_states_seen": self.total_states_seen,
            "decisions_evicted": self.total_decisions_seen - len(self.decision_memory)
        }
    
    def get_memory_snapshot(self) -> Dict[str, Any]:
        """Get complete memory snapshot for export.
        
        Returns:
            Dictionary with complete memory state
        """
        return {
            "agent_id": self.agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "memory_stats": self.get_memory_stats(),
            "recent_decisions": [d.to_dict() for d in self.decision_memory],
            "app_states": {
                app_id: [s.to_dict() for s in states]
                for app_id, states in self.app_state_memory.items()
            }
        }
    
    def load_memory_snapshot(self, snapshot: Dict[str, Any]):
        """Load memory state from snapshot.
        
        Args:
            snapshot: Memory snapshot dictionary
        """
        # Load decisions
        self.decision_memory.clear()
        for decision_dict in snapshot.get("recent_decisions", []):
            record = DecisionRecord(**decision_dict)
            self.decision_memory.append(record)
        
        # Load app states
        self.app_state_memory.clear()
        for app_id, states_list in snapshot.get("app_states", {}).items():
            self.app_state_memory[app_id] = deque(maxlen=self.max_states_per_app)
            for state_dict in states_list:
                snapshot_obj = AppStateSnapshot(**state_dict)
                self.app_state_memory[app_id].append(snapshot_obj)
    
    def clear_memory(self):
        """Clear all memory."""
        self.decision_memory.clear()
        self.app_state_memory.clear()
        self.total_decisions_seen = 0
        self.total_states_seen = 0
    
    def to_json(self, filepath: str):
        """Save memory snapshot to JSON file.
        
        Args:
            filepath: Path to save JSON file
        """
        snapshot = self.get_memory_snapshot()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2)
    
    def from_json(self, filepath: str):
        """Load memory snapshot from JSON file.
        
        Args:
            filepath: Path to JSON file
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)
        self.load_memory_snapshot(snapshot)
    
    def get_memory_context(self, entity_id: Optional[str] = None, lookback: int = 10) -> Dict[str, Any]:
        """Get memory context for decision-making.
        
        Computes memory signals that influence decisions:
        - recent_failures: Count of failed decisions
        - recent_actions: List of recent action types
        - repeated_actions: Count of repeated consecutive actions
        - instability_score: 0-100 score based on failure rate
        - last_action_outcome: Most recent decision outcome
        
        Args:
            entity_id: Optional entity (app_id) to filter by
            lookback: Number of recent decisions to analyze
            
        Returns:
            Dictionary with memory signals
        """
        recent_decisions = self.recall_recent_decisions(lookback)
        
        # Filter by entity if provided
        if entity_id:
            recent_decisions = [
                d for d in recent_decisions 
                if d.context and d.context.get('app_id') == entity_id
            ]
        
        # Extract memory signals
        recent_failures = sum(1 for d in recent_decisions if d.outcome in ['failure', 'failed', 'error'])
        recent_successes = sum(1 for d in recent_decisions if d.outcome in ['success', 'executed'])
        
        # Recent actions (extract action types)
        recent_actions = []
        for d in recent_decisions:
            action = d.decision_data.get('rl_action', d.decision_data.get('action', 'unknown'))
            recent_actions.append(str(action))
        
        # Detect repeated consecutive actions
        repeated_actions = 0
        if len(recent_actions) >= 2:
            consecutive_count = 1
            for i in range(1, len(recent_actions)):
                if recent_actions[i] == recent_actions[i-1]:
                    consecutive_count += 1
                else:
                    consecutive_count = 1
                repeated_actions = max(repeated_actions, consecutive_count)
        
        # Instability score (0-100, higher = more unstable)
        total_decisions = len(recent_decisions)
        if total_decisions > 0:
            failure_rate = recent_failures / total_decisions
            instability_score = int(failure_rate * 100)
        else:
            instability_score = 0
        
        # Last action outcome
        last_action_outcome = None
        if recent_decisions:
            last_action_outcome = recent_decisions[-1].outcome
        
        # App-specific context if entity_id provided
        app_context = None
        if entity_id:
            app_state = self.get_app_current_state(entity_id)
            if app_state:
                app_context = {
                    'current_status': app_state.status,
                    'health': app_state.health,
                    'recent_events': app_state.recent_events
                }
        
        return {
            'recent_failures': recent_failures,
            'recent_successes': recent_successes,
            'recent_actions': recent_actions,
            'repeated_actions': repeated_actions,
            'instability_score': instability_score,
            'last_action_outcome': last_action_outcome,
            'total_recent_decisions': total_decisions,
            'entity_id': entity_id,
            'app_context': app_context
        }
    
    def should_override_decision(
        self, 
        entity_id: Optional[str] = None,
        failure_threshold: int = 3,
        repetition_threshold: int = 3
    ) -> Dict[str, Any]:
        """Check if memory suggests overriding the decision.
        
        Args:
            entity_id: Optional entity to check
            failure_threshold: Number of recent failures to trigger override
            repetition_threshold: Number of repeated actions to trigger override
            
        Returns:
            Dictionary with override recommendation
        """
        context = self.get_memory_context(entity_id)
        override_decision = None
        override_reason = None
        override_applied = False
        
        return {
            'override_applied': override_applied,
            'override_decision': override_decision,
            'override_reason': override_reason,
            'memory_signals': context
        }
    
    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_memory_stats()
        return (
            f"AgentMemory(decisions={stats['decision_count']}/{self.max_decisions}, "
            f"apps={stats['app_count']}, states={stats['total_app_states']})"
        )
