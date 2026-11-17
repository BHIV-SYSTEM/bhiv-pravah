"""
RL Decision Layer - Autonomous action selection for CI/CD events
"""

import json
import random
import os
from typing import Dict, Any

class RLDecisionLayer:
    def __init__(self, env='dev'):
        self.env = env
        self.q_table_path = f"logs/{env}/rl_q_table.json"
        self.q_table = self.load_q_table()
        
        # Action mappings for different failure types
        self.action_map = {
            'crash': ['restart', 'noop'],
            'overload': ['scale_up', 'noop'], 
            'false_alarm': ['noop'],
            'latency': ['restart', 'scale_up'],
            'memory_leak': ['restart']
        }
    
    def load_q_table(self) -> Dict[str, Dict[str, float]]:
        """Load Q-table from file or initialize"""
        if os.path.exists(self.q_table_path):
            try:
                with open(self.q_table_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Initialize with default values
        return {
            'crash': {'restart': 0.8, 'noop': 0.1},
            'overload': {'scale_up': 0.7, 'noop': 0.3},
            'false_alarm': {'noop': 0.9},
            'latency': {'restart': 0.6, 'scale_up': 0.4},
            'memory_leak': {'restart': 0.9}
        }
    
    def save_q_table(self):
        """Save Q-table to file"""
        os.makedirs(os.path.dirname(self.q_table_path), exist_ok=True)
        with open(self.q_table_path, 'w') as f:
            json.dump(self.q_table, f, indent=2)
    
    def choose_action(self, state: str) -> str:
        """Choose best action for given state"""
        if state not in self.q_table:
            # Default to noop for unknown states
            return 'noop'
        
        state_actions = self.q_table[state]
        if not state_actions:
            return 'noop'
        
        # Choose action with highest Q-value (with small epsilon for exploration)
        if random.random() < 0.1:  # 10% exploration
            return random.choice(list(state_actions.keys()))
        else:
            return max(state_actions.items(), key=lambda x: x[1])[0]
    
    def process_state(self, event_data: Dict[str, Any]) -> int:
        """Process runtime event and return action index"""
        try:
            event_type = event_data.get('event_type', 'unknown')
            action_str = self.choose_action(event_type)
            
            # Map string actions to indices for compatibility
            action_map = {
                'noop': 0,
                'restart': 1, 
                'scale_up': 2,
                'scale_down': 3,
                'rollback': 4
            }
            
            return action_map.get(action_str, 0)  # Default to noop (0)
        except Exception as e:
            # Log error and return safe default
            print(f"RL processing error: {e}")
            return 0  # Safe default: noop
    
    def update_q_value(self, state: str, action: str, reward: float, learning_rate: float = 0.1):
        """Update Q-value based on reward"""
        if state not in self.q_table:
            self.q_table[state] = {}
        
        if action not in self.q_table[state]:
            self.q_table[state][action] = 0.0
        
        # Q-learning update rule
        old_value = self.q_table[state][action]
        self.q_table[state][action] = old_value + learning_rate * (reward - old_value)
        
        self.save_q_table()