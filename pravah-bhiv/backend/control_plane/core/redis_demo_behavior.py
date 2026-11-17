#!/usr/bin/env python3
"""Redis Demo Behavior - No Silent Mock Mode"""

import logging
from typing import Dict, Any, Optional
from control_plane.core.redis_stability import RedisStabilityManager, RedisConnectionError

class RedisUnavailableError(Exception):
    """Raised when Redis is unavailable and no explicit stub is configured."""
    pass

def get_redis_bus_demo_safe(env: str, use_stub: bool = False):
    """Get Redis bus with demo-safe behavior - no silent fallback.
    
    Args:
        env: Environment name
        use_stub: If True, use explicit stub when Redis unavailable
        
    Returns:
        Redis bus or explicit stub
        
    Raises:
        RedisUnavailableError: If Redis unavailable and no stub requested
    """
    try:
        return RedisStabilityManager.get_redis_connection(env, allow_stub=use_stub)
    except RedisConnectionError as e:
        # Convert to expected exception type for backward compatibility
        raise RedisUnavailableError(str(e))

def validate_redis_for_demo(env: str) -> Dict[str, Any]:
    """Validate Redis availability for demo environment.
    
    Returns:
        Status dictionary with connection info
    """
    from control_plane.core.redis_stability import validate_redis_stability
    return validate_redis_stability(env)