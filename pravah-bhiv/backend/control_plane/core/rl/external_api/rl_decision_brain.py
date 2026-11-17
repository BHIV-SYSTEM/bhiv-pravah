"""
Universal DevOps Runtime Intelligence (RL Decision Brain)
Demo-Frozen Version - Learning Disabled for Demo Safety
"""

import json
import time
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

class Environment(Enum):
    DEV = "dev"
    STAGE = "stage" 
    PROD = "prod"

class Action(Enum):
    NOOP = "noop"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    RESTART = "restart"
    ROLLBACK = "rollback"  # Disabled in demo

class EventType(Enum):
    CRASH = "crash"
    OVERLOAD = "overload"
    FALSE_FAILURE = "false_failure"

class RLDecisionBrain:
    """
    Demo-Frozen RL Decision Engine
    - Learning disabled (epsilon = 0)
    - Deterministic behavior guaranteed
    - Action scope enforced per environment
    """
    
    def __init__(self, demo_mode: bool = True):
        self.demo_mode = demo_mode
        self.exploration_rate = 0.0  # FROZEN: No exploration during demo
        self.learning_enabled = False  # FROZEN: No Q-table updates
        
        # Environment-specific allowed actions (FINAL LOCK)
        self.allowed_actions = {
            Environment.DEV: [Action.NOOP, Action.SCALE_UP, Action.SCALE_DOWN, Action.RESTART],
            Environment.STAGE: [Action.NOOP, Action.SCALE_UP, Action.SCALE_DOWN],
            Environment.PROD: [Action.NOOP, Action.RESTART]
        }
        
        # Frozen decision table (deterministic mapping)
        self.decision_table = {
            (Environment.DEV, EventType.CRASH): Action.RESTART,
            (Environment.DEV, EventType.OVERLOAD): Action.SCALE_UP,
            (Environment.DEV, EventType.FALSE_FAILURE): Action.NOOP,
            
            (Environment.STAGE, EventType.CRASH): Action.NOOP,  # Conservative
            (Environment.STAGE, EventType.OVERLOAD): Action.SCALE_UP,
            (Environment.STAGE, EventType.FALSE_FAILURE): Action.NOOP,
            
            (Environment.PROD, EventType.CRASH): Action.RESTART,
            (Environment.PROD, EventType.OVERLOAD): Action.NOOP,  # Conservative
            (Environment.PROD, EventType.FALSE_FAILURE): Action.NOOP,
        }
        
        logging.info("RL Decision Brain initialized in DEMO MODE - Learning FROZEN")
    
    def make_decision(self, environment: Environment, event_type: EventType, 
                     event_data: Dict) -> Dict:
        """
        Make deterministic decision based on frozen decision table
        Guarantees identical output for identical input
        """
        timestamp = time.time()
        
        # Get deterministic decision from frozen table
        decision_key = (environment, event_type)
        proposed_action = self.decision_table.get(decision_key, Action.NOOP)
        
        # Enforce action scope filtering BEFORE emission
        if proposed_action not in self.allowed_actions[environment]:
            logging.warning(f"Action {proposed_action} not allowed in {environment}, defaulting to NOOP")
            final_action = Action.NOOP
            action_filtered = True
        else:
            final_action = proposed_action
            action_filtered = False
        
        # Create decision output
        decision = {
            "timestamp": timestamp,
            "environment": environment.value,
            "event_type": event_type.value,
            "event_data": event_data,
            "proposed_action": proposed_action.value,
            "final_action": final_action.value,
            "action_filtered": action_filtered,
            "demo_mode": self.demo_mode,
            "learning_enabled": self.learning_enabled,
            "exploration_rate": self.exploration_rate
        }
        
        logging.info(f"Decision made: {environment.value} -> {final_action.value}")
        return decision
    
    def get_system_status(self) -> Dict:
        """Return current system configuration for demo visibility"""
        return {
            "demo_mode": self.demo_mode,
            "learning_enabled": self.learning_enabled,
            "exploration_rate": self.exploration_rate,
            "allowed_actions": {
                env.value: [action.value for action in actions] 
                for env, actions in self.allowed_actions.items()
            }
        }