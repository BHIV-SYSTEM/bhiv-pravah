import json
import os
import numpy as np
from collections import defaultdict
import csv
import datetime
from control_plane.core.stage_determinism import StageDeterminismLock, log_determinism_status
from control_plane.core.rl_decision_layer import RLDecisionLayer as OriginalRLDecisionLayer

class RLDecisionLayer(OriginalRLDecisionLayer):
    """Ritesh's original RL Decision Layer with Q-learning."""
    pass

class RLOptimizer:
    """Compatibility wrapper for existing system using Ritesh's RL Decision Layer."""
    
    def __init__(self, q_table_file, performance_log_file, env='dev'):
        self.env = env
        self.q_table_file = q_table_file
        self.performance_log_file = performance_log_file
        self.states = ["deployment_failure", "latency_issue", "anomaly_score", "anomaly_health"]
        self.actions = ["retry_deployment", "restore_previous_version", "adjust_thresholds"]
        
        # Stage environment: Disable exploration for predictable demo behavior
        if StageDeterminismLock.is_stage_env(env):
            epsilon = StageDeterminismLock.disable_exploration()  # No exploration in stage
            log_determinism_status(env, "RL Optimizer exploration")
            print(f"Stage environment: RL exploration disabled (epsilon={epsilon})")
        else:
            epsilon = 0.2  # Exploration rate for dev/prod
        
        # Initialize Ritesh's RL Decision Layer via safe wiring
        from control_plane.core.rl_wiring import get_rl_wiring
        self.rl_wiring = get_rl_wiring(env)
        
        self._init_performance_log()
        print("Initialized RL Optimizer with Ritesh's Decision Layer.")

    def _init_performance_log(self):
        """Initialize performance log file."""
        os.makedirs(os.path.dirname(self.performance_log_file), exist_ok=True)
        if not os.path.exists(self.performance_log_file):
            with open(self.performance_log_file, 'w', newline='') as f:
                csv.writer(f).writerow(["timestamp", "state", "action", "reward"])

    def _state_to_dict(self, state):
        """Convert state string to dict for RL layer."""
        return {"failure_type": state, "env": self.env}

    def choose_action(self, state):
        """Choose action using safe RL wiring layer."""
        runtime_event = {'event_type': 'failure', 'status': state, 'env': self.env}
        normalized_event = self.rl_wiring.normalize_runtime_event(runtime_event)
        decision = self.rl_wiring.get_safe_decision(normalized_event)
        
        # Map safe action back to system actions
        action_mapping = {
            'retry_deployment': 'retry_deployment',
            'restart_service': 'restore_previous_version', 
            'adjust_thresholds': 'adjust_thresholds',
            'noop': 'retry_deployment'  # Default fallback
        }
        
        action = action_mapping.get(str(decision['action']), 'retry_deployment')
        
        if StageDeterminismLock.is_stage_env(self.env):
            print(f"RL Optimizer (STAGE): Safe decision -> {action}")
        else:
            print(f"RL Optimizer: Safe decision -> {action} (validated={decision['validated']})")
        
        return action

    def learn(self, state, action, reward):
        """Update Q-table using safe RL wiring layer."""
        runtime_event = {'event_type': 'failure', 'status': state, 'env': self.env}
        next_event = {'event_type': 'resolved', 'status': 'success', 'env': self.env}
        
        normalized_event = self.rl_wiring.normalize_runtime_event(runtime_event)
        
        # Get RL index for the action taken
        reverse_mapping = {'retry_deployment': 2, 'restore_previous_version': 1, 'adjust_thresholds': 3}
        rl_index = reverse_mapping.get(action, 0)
        
        reward_change = self.rl_wiring.record_outcome(normalized_event, rl_index, reward, next_event)
        
        # Log performance
        timestamp = datetime.datetime.now().isoformat()
        with open(self.performance_log_file, 'a', newline='') as f:
            csv.writer(f).writerow([timestamp, state, action, reward])
        
        print(f"RL Update: {state}/{action}: reward={reward}, change={reward_change:.3f}")

    def save_q_table(self):
        """Save Q-table using safe RL wiring layer."""
        self.rl_wiring.rl_layer.save_summary()
        print(f"Q-table saved to {self.rl_wiring.rl_layer.summary_file}")