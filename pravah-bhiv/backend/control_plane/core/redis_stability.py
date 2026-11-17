#!/usr/bin/env python3
"""
Redis Stability Module
Removes silent Redis mock fallback - ensures deterministic behavior
"""

import logging
import os
from typing import Optional, Dict, Any

class RedisConnectionError(Exception):
    """Raised when Redis connection fails and no explicit fallback is configured."""
    pass

class RedisStabilityManager:
    """Manages Redis connections with explicit fallback behavior - no silent mocking."""
    
    @staticmethod
    def get_redis_connection(env: str, allow_stub: bool = False):
        """
        Get Redis connection with explicit fallback behavior.
        
        Args:
            env: Environment name
            allow_stub: If True, use explicit stub when Redis unavailable
            
        Returns:
            Redis connection or explicit stub
            
        Raises:
            RedisConnectionError: If Redis unavailable and no stub allowed
        """
        try:
            # Attempt real Redis connection
            from control_plane.core.redis_event_bus import get_redis_bus
            redis_bus = get_redis_bus(env)
            
            # Test connection with a ping
            redis_bus.publish("stability.test", {"test": True})
            
            print(f"Redis connection established for {env.upper()}")
            logging.info(f"Redis active for {env}")
            return redis_bus
            
        except Exception as redis_error:
            # Log hard warning - no silent failures
            warning_msg = f"REDIS CONNECTION FAILED in {env.upper()}: {redis_error}"
            print(f"WARNING: {warning_msg}")
            logging.error(warning_msg)
            
            if allow_stub:
                # Use explicit stub - not silent fallback
                print(f"Using EXPLICIT Redis stub for {env.upper()}")
                logging.warning(f"Redis stub active for {env} - not production ready")
                return RedisStub(env)
            else:
                # Fail deterministically - no silent operation
                error_msg = f"Redis unavailable in {env} and no explicit stub configured"
                print(f"ERROR: {error_msg}")
                raise RedisConnectionError(error_msg)

class RedisStub:
    """Explicit Redis stub - not a silent mock."""
    
    def __init__(self, env: str):
        self.env = env
        self.message_store = []
        print(f"EXPLICIT REDIS STUB initialized for {env.upper()}")
        logging.warning(f"Using Redis stub for {env} - not suitable for production")
    
    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """Stub publish - stores messages locally."""
        self.message_store.append({
            'channel': channel,
            'message': message,
            'env': self.env,
            'timestamp': os.path.basename(__file__)  # Use os.path for stability
        })
        print(f"STUB: Published to {channel} (stored locally)")
        return True
    
    def get_messages(self) -> list:
        """Get all stored messages from stub."""
        return self.message_store.copy()
    
    def clear_messages(self) -> None:
        """Clear stored messages."""
        self.message_store.clear()

def validate_redis_stability(env: str) -> Dict[str, Any]:
    """
    Validate Redis stability for environment.
    
    Returns:
        Status dictionary with connection info
    """
    try:
        redis_conn = RedisStabilityManager.get_redis_connection(env, allow_stub=False)
        return {
            'status': 'connected',
            'env': env,
            'type': 'redis',
            'message': f'Redis stable connection for {env}',
            'stable': True
        }
    except RedisConnectionError:
        return {
            'status': 'unavailable',
            'env': env,
            'type': 'none',
            'message': f'Redis unavailable for {env} - no stub configured',
            'stable': False,
            'recommendation': f'Use allow_stub=True for demo purposes'
        }
    except Exception as e:
        return {
            'status': 'error',
            'env': env,
            'type': 'unknown',
            'message': f'Redis stability validation error: {e}',
            'stable': False
        }