#!/usr/bin/env python3
"""
Redis-based External Event Bus
Replaces internal bus with Redis pub/sub for multi-agent communication
"""

import os
import json
import time
import threading
import datetime
import uuid
from typing import Dict, List, Callable, Any
import redis
from control_plane.core.env_config import EnvironmentConfig
from security.signing import sign_payload
from security.nonce_store import check_nonce

class RedisEventBus:
    """External event bus using Redis pub/sub."""
    
    def __init__(self, env=None):
        self.env_config = EnvironmentConfig(env)
        self.redis_host = os.getenv('REDIS_HOST') or self.env_config.get('redis_host', 'redis')
        raw_port = os.getenv('REDIS_PORT') or self.env_config.get('redis_port', 6380 if self.env_config.env == 'prod' else 6379)
        self.redis_port = int(raw_port)
        self.redis_db = int(os.getenv('REDIS_DB') or self.env_config.get('redis_db', 2 if self.env_config.env == 'prod' else 0))
        
        # Initialize Redis connection
        self.redis_client = None
        self.pubsub = None
        self.subscribers = {}
        self.message_history = []
        self.running = False
        self.listener_thread = None
        
        self._connect()
    
    def _connect(self):
        """Connect to Redis server with retries."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                self.redis_client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    db=self.redis_db,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                
                # Test connection
                self.redis_client.ping()
                self.pubsub = self.redis_client.pubsub()
                print(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
                return
                
            except redis.ConnectionError as e:
                print(f"Failed to connect to Redis (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
        
        # Fallback to mock mode if all retries fail
        self._setup_mock_mode()
    
    def _setup_mock_mode(self):
        """Setup mock mode when Redis is unavailable."""
        print("Running in mock mode (Redis unavailable)")
        self.redis_client = None
        self.pubsub = None
    
    def publish(self, event_type: str, data: Dict[str, Any]):
        """Publish event to Redis channel with signature."""
        # Add nonce for replay protection
        nonce = str(uuid.uuid4())
        
        message = {
            'event_type': event_type,
            'data': data,
            'timestamp': datetime.datetime.now().isoformat(),
            'environment': self.env_config.get('environment'),
            'nonce': nonce
        }
        
        # Sign the message
        message = sign_payload(message)
        
        # Store in history
        self.message_history.append(message)
        if len(self.message_history) > 1000:  # Keep last 1000 messages
            self.message_history.pop(0)
        
        if self.redis_client:
            try:
                channel = f"cicd.{event_type}"
                self.redis_client.publish(channel, json.dumps(message))
                print(f"Published to {channel}: {event_type}")
            except redis.RedisError as e:
                print(f"Failed to publish message: {e}")
        else:
            # Mock mode - just print
            print(f"[MOCK] Published: {event_type} -> {data}")
    
    def subscribe(self, event_pattern: str, callback: Callable):
        """Subscribe to event pattern."""
        if event_pattern not in self.subscribers:
            self.subscribers[event_pattern] = []
        
        self.subscribers[event_pattern].append(callback)
        
        if self.redis_client and self.pubsub:
            try:
                channel_pattern = f"cicd.{event_pattern}"
                self.pubsub.psubscribe(channel_pattern)
                print(f"Subscribed to pattern: {channel_pattern}")
                
                # Start listener thread if not running
                if not self.running:
                    self.start_listener()
                    
            except redis.RedisError as e:
                print(f"Failed to subscribe: {e}")
        else:
            print(f"[MOCK] Subscribed to: {event_pattern}")
    
    def start_listener(self):
        """Start Redis message listener thread."""
        if self.running or not self.pubsub:
            return
        
        self.running = True
        self.listener_thread = threading.Thread(target=self._listen_for_messages, daemon=True)
        self.listener_thread.start()
        print("Redis listener thread started")
    
    def _listen_for_messages(self):
        """Listen for Redis pub/sub messages."""
        try:
            for message in self.pubsub.listen():
                if not self.running:
                    break
                
                if message['type'] == 'pmessage':
                    try:
                        data = json.loads(message['data'])
                        event_type = data['event_type']
                        
                        # Find matching subscribers
                        for pattern, callbacks in self.subscribers.items():
                            if self._pattern_matches(pattern, event_type):
                                for callback in callbacks:
                                    try:
                                        callback(event_type, data['data'])
                                    except Exception as e:
                                        print(f"Callback error: {e}")
                    
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"Invalid message format: {e}")
                        
        except Exception as e:
            print(f"Listener error: {e}")
        finally:
            self.running = False
    
    def _pattern_matches(self, pattern: str, event_type: str) -> bool:
        """Check if event type matches subscription pattern."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return pattern == event_type
    
    def get_message_history(self, limit: int = 100) -> List[Dict]:
        """Get recent message history."""
        return self.message_history[-limit:]
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get Redis queue statistics."""
        stats = {
            'connected': self.redis_client is not None,
            'subscribers': len(self.subscribers),
            'message_history_count': len(self.message_history),
            'environment': self.env_config.get('environment')
        }
        
        if self.redis_client:
            try:
                info = self.redis_client.info()
                stats.update({
                    'redis_version': info.get('redis_version'),
                    'connected_clients': info.get('connected_clients'),
                    'used_memory_human': info.get('used_memory_human'),
                    'total_commands_processed': info.get('total_commands_processed')
                })
            except redis.RedisError:
                stats['redis_error'] = True
        
        return stats
    
    def stop(self):
        """Stop the event bus."""
        self.running = False
        if self.pubsub:
            try:
                self.pubsub.close()
            except:
                pass
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=1)
        print("Redis event bus stopped")

# Global Redis event bus instance
redis_bus = None

def get_redis_bus(env=None) -> RedisEventBus:
    """Get or create Redis event bus instance."""
    global redis_bus
    if redis_bus is None:
        redis_bus = RedisEventBus(env)
    return redis_bus