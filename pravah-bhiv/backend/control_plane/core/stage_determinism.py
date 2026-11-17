#!/usr/bin/env python3
"""
Stage Determinism Lock
Ensures predictable behavior for live demos in stage environment
"""

import hashlib
import os

class StageDeterminismLock:
    """Ensures deterministic behavior in stage environment."""
    
    @staticmethod
    def is_stage_env(env):
        """Check if current environment is stage."""
        return env == 'stage'
    
    @staticmethod
    def deterministic_choice(choices, seed_input):
        """Make deterministic choice based on seed input."""
        if not choices:
            return None
        
        # Create deterministic hash from seed input
        seed_str = str(seed_input)
        hash_obj = hashlib.md5(seed_str.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        # Use hash to select from choices
        index = hash_int % len(choices)
        return choices[index]
    
    @staticmethod
    def get_fixed_timing(base_time_ms=1200):
        """Return fixed timing for stage environment."""
        return base_time_ms
    
    @staticmethod
    def disable_exploration():
        """Return epsilon=0 for RL in stage."""
        return 0.0
    
    @staticmethod
    def get_deterministic_response_time(action_type, worker_id=1):
        """Get deterministic response time based on action and worker."""
        base_times = {
            'deploy': 1200,
            'scale': 800,
            'restart': 600,
            'heal': 150
        }
        
        base = base_times.get(action_type, 1000)
        # Add small deterministic variation based on worker
        variation = (worker_id - 1) * 50
        return base + variation

def ensure_stage_determinism(env):
    """Decorator to ensure deterministic behavior in stage."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if StageDeterminismLock.is_stage_env(env):
                # Force deterministic behavior
                kwargs['deterministic'] = True
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Global flag for stage determinism
STAGE_DETERMINISM_ENABLED = os.getenv('STAGE_DETERMINISM', 'true').lower() == 'true'

def log_determinism_status(env, component):
    """Log determinism status for debugging."""
    if StageDeterminismLock.is_stage_env(env):
        print(f"STAGE DETERMINISM: {component} locked to predictable behavior")
    else:
        print(f"{component} using normal random behavior in {env}")