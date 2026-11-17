#!/usr/bin/env python3
"""
RL Response Validator
Safety validation layer for external RL API responses
Enforces: Unsafe output → refuse → NOOP
"""

from typing import Dict, Any, Tuple


class RLResponseValidator:
    """
    Validates RL API responses for safety and correctness
    
    Validation Rules:
    1. Structure validation - required fields present
    2. Action bounds - action within valid range (0-4)
    3. Safety classification - action allowed for environment
    
    Enforcement:
    - Invalid response → NOOP (action=0)
    - Unsafe action → NOOP (action=0)
    - Valid safe action → Pass through
    """
    
    # Valid action range
    MIN_ACTION = 0  # NOOP
    MAX_ACTION = 4  # ROLLBACK
    
    # Action names for logging
    ACTION_NAMES = {
        0: 'NOOP',
        1: 'RESTART',
        2: 'SCALE_UP',
        3: 'SCALE_DOWN',
        4: 'ROLLBACK'
    }
    
    def __init__(self, env: str = 'dev'):
        self.env = env
        
        # Environment-specific safety rules (matches rl_orchestrator_safe.py)
        self.safety_rules = {
            'prod': [0],  # Production only allows NOOP
            'stage': [0, 1],  # Stage allows NOOP and RESTART
            'dev': [0, 1, 2, 3]  # Dev allows most actions except ROLLBACK
        }
    
    def validate_response(self, response_data: Dict[str, Any]) -> Tuple[bool, int, str]:
        """
        Validate RL API response
        
        Args:
            response_data: API response dictionary
            
        Returns:
            Tuple of (is_valid, action, reason)
            - is_valid: True if response is valid and safe
            - action: Validated action (0 if invalid/unsafe)
            - reason: Explanation of validation result
        """
        from core.proof_logger import write_proof, ProofEvents
        
        # 1. Structure validation
        if not isinstance(response_data, dict):
            write_proof(ProofEvents.RL_VALIDATION_FAILED, {
                'env': self.env,
                'reason': 'Invalid response structure - not a dictionary',
                'response': str(response_data),
                'fallback_action': 0
            })
            return (False, 0, "Invalid response structure - not a dictionary")
        
        # 2. Check for 'action' field
        if 'action' not in response_data:
            write_proof(ProofEvents.RL_VALIDATION_FAILED, {
                'env': self.env,
                'reason': 'Missing required field: action',
                'response': response_data,
                'fallback_action': 0
            })
            return (False, 0, "Missing required field: action")
        
        action = response_data.get('action')
        
        # 3. Action type validation
        if not isinstance(action, int):
            try:
                action = int(action)
            except (ValueError, TypeError):
                write_proof(ProofEvents.RL_VALIDATION_FAILED, {
                    'env': self.env,
                    'reason': f'Invalid action type: {type(action).__name__}',
                    'action': str(action),
                    'fallback_action': 0
                })
                return (False, 0, f"Invalid action type: {type(action).__name__}")
        
        # 4. Action bounds validation
        if not (self.MIN_ACTION <= action <= self.MAX_ACTION):
            write_proof(ProofEvents.RL_VALIDATION_FAILED, {
                'env': self.env,
                'reason': f'Action out of bounds: {action} (valid range: {self.MIN_ACTION}-{self.MAX_ACTION})',
                'action': action,
                'fallback_action': 0
            })
            return (False, 0, f"Action out of bounds: {action}")
        
        # 5. Safety validation - check if action is allowed for environment
        allowed_actions = self.safety_rules.get(self.env, [0])
        if action not in allowed_actions:
            action_name = self.ACTION_NAMES.get(action, f'UNKNOWN({action})')
            write_proof(ProofEvents.RL_UNSAFE_REFUSED, {
                'env': self.env,
                'action': action,
                'action_name': action_name,
                'reason': f'Action {action_name} not allowed for {self.env} environment',
                'allowed_actions': allowed_actions,
                'fallback_action': 0
            })
            return (False, 0, f"Unsafe action {action_name} for {self.env} environment")
        
        # 6. Check for API error flag in response
        if response_data.get('error') or response_data.get('fallback'):
            write_proof(ProofEvents.RL_VALIDATION_FAILED, {
                'env': self.env,
                'reason': 'API returned error or fallback flag',
                'response': response_data,
                'fallback_action': 0
            })
            return (False, 0, f"API error: {response_data.get('error', 'Unknown error')}")
        
        # All validations passed
        action_name = self.ACTION_NAMES.get(action, f'UNKNOWN({action})')
        write_proof(ProofEvents.RL_VALIDATION_PASSED, {
            'env': self.env,
            'action': action,
            'action_name': action_name,
            'status': 'validated',
            'response': response_data
        })
        
        return (True, action, f"Action {action_name} validated successfully")
    
    def validate_and_sanitize(self, response_data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """
        Validate and sanitize RL API response
        
        Args:
            response_data: API response dictionary
            
        Returns:
            Tuple of (safe_action, metadata)
            - safe_action: Validated action (0 if unsafe)
            - metadata: Validation metadata for logging
        """
        is_valid, action, reason = self.validate_response(response_data)
        
        metadata = {
            'is_valid': is_valid,
            'action': action,
            'reason': reason,
            'original_response': response_data
        }
        
        return (action, metadata)


def validate_rl_response(response_data: Dict[str, Any], env: str = 'dev') -> Tuple[int, Dict[str, Any]]:
    """
    Convenience function to validate RL API response
    
    Args:
        response_data: API response dictionary
        env: Environment name
        
    Returns:
        Tuple of (safe_action, validation_metadata)
    """
    validator = RLResponseValidator(env=env)
    return validator.validate_and_sanitize(response_data)
