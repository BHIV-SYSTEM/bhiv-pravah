#!/usr/bin/env python3
"""
RL Wiring Layer - Safe Runtime → RL → Orchestrator Pipeline
Connects normalized runtime events to Ritesh's RL Decision Layer safely
"""

from rl_decision_layer import RLDecisionLayer
from core.prod_safety import validate_prod_action, ProductionSafetyError

class RLWiringLayer:
    """Safe wiring between runtime events and RL decision layer."""
    
    # Safe action mapping from RL indices to orchestrator actions
    SAFE_ACTIONS = {
        0: 'noop',
        1: 'restart_service', 
        2: 'retry_deployment',
        3: 'adjust_thresholds',
        4: 'scale_workers',
        5: 'emit_events',
        6: 'log_actions',
        7: 'update_metrics'
    }
    
    def __init__(self, env='dev'):
        self.env = env
        self.rl_layer = RLDecisionLayer(
            state_space_size=100,
            action_space_size=len(self.SAFE_ACTIONS),
            learning_rate=0.1,
            discount_factor=0.9,
            epsilon=0.0 if env == 'stage' else 0.1
        )
    
    def normalize_runtime_event(self, event):
        """Convert runtime event to normalized RL state."""
        return {
            'event_type': event.get('event_type', 'unknown'),
            'status': event.get('status', 'unknown'),
            'env': self.env,
            'response_time_bucket': self._bucket_response_time(event.get('response_time', 0))
        }
    
    def _bucket_response_time(self, response_time):
        """Bucket response times for state normalization."""
        if response_time < 100: return 'fast'
        elif response_time < 500: return 'normal'
        elif response_time < 1000: return 'slow'
        else: return 'critical'
    
    def get_safe_decision(self, normalized_event):
        """Get validated safe decision from RL layer."""
        rl_action_idx = self.rl_layer.process_state(normalized_event)
        safe_action = self.SAFE_ACTIONS.get(rl_action_idx % len(self.SAFE_ACTIONS), 'noop')
        
        # Production safety validation
        try:
            validate_prod_action(safe_action, self.env)
            return {
                'action': safe_action,
                'rl_index': rl_action_idx,
                'validated': True,
                'reason': 'rl_decision'
            }
        except ProductionSafetyError:
            return {
                'action': 'noop',
                'rl_index': 0,
                'validated': False,
                'reason': 'prod_safety_block'
            }
    
    def record_outcome(self, normalized_event, rl_index, reward, next_event):
        """Record action outcome back to RL layer."""
        next_normalized = self.normalize_runtime_event(next_event)
        return self.rl_layer.record_action_result(
            normalized_event, rl_index, reward, next_normalized
        )

def get_rl_wiring(env='dev'):
    """Get RL wiring layer for environment."""
    return RLWiringLayer(env)