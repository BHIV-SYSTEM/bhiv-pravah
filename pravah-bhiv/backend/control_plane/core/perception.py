#!/usr/bin/env python3
"""
Perception Layer - Environmental Awareness
Unified perception layer that aggregates inputs from multiple sources for the autonomous agent.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class PerceptionType(Enum):
    """Types of perceptions the agent can receive."""
    RUNTIME_EVENT = "runtime_event"
    HEALTH_SIGNAL = "health_signal"
    ONBOARDING_INPUT = "onboarding_input"
    SYSTEM_ALERT = "system_alert"


class PerceptionPriority(Enum):
    """Priority levels for perceptions."""
    CRITICAL = 10
    HIGH = 7
    MEDIUM = 5
    LOW = 3
    INFO = 1


@dataclass
class Perception:
    """A single perception from the environment."""
    type: str  # PerceptionType value
    source: str  # redis, monitoring, user_input, etc.
    timestamp: str
    data: Dict[str, Any]
    priority: int  # 1-10, higher = more important
    perception_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def __post_init__(self):
        """Generate perception ID if not provided."""
        if self.perception_id is None:
            self.perception_id = f"{self.type}_{self.timestamp}_{id(self)}"


class PerceptionLayer:
    """Unified perception layer for the autonomous agent.
    
    Aggregates perceptions from multiple sources (runtime events, health signals, onboarding).
    """
    
    def __init__(self, agent_id: str):
        """Initialize perception layer.
        
        Args:
            agent_id: Agent identifier
        """
        self.agent_id = agent_id
        self.perception_adapters: List[Any] = []
        self.perception_history: List[Perception] = []
        self.max_history = 100  # Keep last 100 perceptions
    
    def register_adapter(self, adapter):
        """Register a perception adapter.
        
        Args:
            adapter: Perception adapter instance
        """
        self.perception_adapters.append(adapter)
    
    def perceive(self) -> List[Perception]:
        """Aggregate all perceptions from registered adapters.
        
        Returns:
            List of perceptions sorted by priority (highest first)
        """
        all_perceptions = []
        
        for adapter in self.perception_adapters:
            try:
                perceptions = adapter.perceive()
                all_perceptions.extend(perceptions)
            except Exception as e:
                # Log error but don't fail entire perception
                print(f"Perception adapter error: {adapter.__class__.__name__}: {e}")
        
        # Sort by priority (highest first)
        all_perceptions.sort(key=lambda p: p.priority, reverse=True)
        
        # Store in history
        self.perception_history.extend(all_perceptions)
        
        # Trim history if needed
        if len(self.perception_history) > self.max_history:
            self.perception_history = self.perception_history[-self.max_history:]
        
        return all_perceptions
    
    def filter_by_type(self, perceptions: List[Perception], perception_type: PerceptionType) -> List[Perception]:
        """Filter perceptions by type.
        
        Args:
            perceptions: List of perceptions
            perception_type: Type to filter by
            
        Returns:
            Filtered perceptions
        """
        return [p for p in perceptions if p.type == perception_type.value]
    
    def filter_by_priority(self, perceptions: List[Perception], min_priority: int) -> List[Perception]:
        """Filter perceptions by minimum priority.
        
        Args:
            perceptions: List of perceptions
            min_priority: Minimum priority level
            
        Returns:
            Perceptions with priority >= min_priority
        """
        return [p for p in perceptions if p.priority >= min_priority]
    
    def get_highest_priority_perception(self, perceptions: List[Perception]) -> Optional[Perception]:
        """Get the highest priority perception.
        
        Args:
            perceptions: List of perceptions
            
        Returns:
            Highest priority perception or None
        """
        if not perceptions:
            return None
        return max(perceptions, key=lambda p: p.priority)
    
    def get_recent_perceptions(self, n: int = 10) -> List[Perception]:
        """Get N most recent perceptions from history.
        
        Args:
            n: Number of perceptions to retrieve
            
        Returns:
            Recent perceptions (most recent last)
        """
        return self.perception_history[-n:] if len(self.perception_history) > n else self.perception_history
    
    def clear_history(self):
        """Clear perception history."""
        self.perception_history.clear()
    
    def get_perception_stats(self) -> Dict[str, Any]:
        """Get perception statistics.
        
        Returns:
            Dictionary with perception stats
        """
        type_counts = {}
        for p in self.perception_history:
            type_counts[p.type] = type_counts.get(p.type, 0) + 1
        
        return {
            "agent_id": self.agent_id,
            "total_perceptions": len(self.perception_history),
            "adapter_count": len(self.perception_adapters),
            "type_breakdown": type_counts,
            "max_history": self.max_history
        }
