
"""
Decision Arbitrator
Mediates between multiple decision sources (RL Brain, Rule-Based, etc.)
"""
# NOT USED in deterministic control plane (Phase 6 cleanup)

from typing import Dict, Any, Optional
import datetime

class DecisionArbitrator:
    """
    Arbitrates between conflicting decisions from different sources.
    Prioritizes based on confidence, source reliability, and safety.
    """
    
    def __init__(self, env='dev'):
        self.env = env
        self.confidence_threshold = 0.7  # specific threshold for RL to be trusted over rules
        
    def arbitrate(self, 
                 rl_decision: Dict[str, Any], 
                 rule_decision: Dict[str, Any],
                 context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Choose the best action from available decisions.
        
        Logic:
        1. If Rule-Based suggests CRITICAL action (e.g. emergency scale down), it might win.
        2. If RL Confidence > Threshold, RL wins.
        3. Else, Rule-Based wins (Fallback).
        """
        
        rl_action = rl_decision.get('action', 'noop')
        rl_confidence = rl_decision.get('confidence', 0.0)
        
        rule_action = rule_decision.get('action', 'noop')
        rule_reason = rule_decision.get('reason', 'rule_default')
        
        # Log inputs for traceability
        arbitration_log = {
            'timestamp': datetime.datetime.now().isoformat(),
            'rl_input': {'action': rl_action, 'confidence': rl_confidence},
            'rule_input': {'action': rule_action, 'reason': rule_reason},
            'context': context
        }
        
        final_decision = {}
        source = "unknown"
        
        # Arbitration Logic
        
        # 1. Critical Rule Check (Optional - for now assuming rules are standard scaling)
        # If rules say "scale_up" and RL says "noop" with low confidence, trust rules.
        
        if rl_confidence >= self.confidence_threshold:
            # Trust RL
            final_decision = rl_decision
            source = "rl_brain"
            reason = f"RL confidence ({rl_confidence}) > threshold ({self.confidence_threshold})"
        else:
            # Fallback to Rules
            final_decision = rule_decision
            source = "rule_based"
            reason = f"RL confidence ({rl_confidence}) too low, falling back to rules. Rule reason: {rule_reason}"
            
        # Structure the output
        output = {
            'action': final_decision.get('action', 'noop'),
            'source': source,
            'reason': reason,
            'confidence': final_decision.get('confidence', 1.0) if source == 'rl_brain' else 1.0,
            'arbitration_details': arbitration_log,
            'original_decisions': {
                'rl': rl_decision,
                'rule': rule_decision
            }
        }
        
        return output
