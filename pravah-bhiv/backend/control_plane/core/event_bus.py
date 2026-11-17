#!/usr/bin/env python3
"""Redis Pub/Sub Event Bus for multi-agent communication"""
import redis
import json
import threading
import time
import csv
import os
from datetime import datetime

class EventBus:
    def __init__(self, redis_host='127.0.0.1', redis_port=6379):
        """Initialize Redis event bus"""
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_client = None
        self.use_redis = False
        self._subscribers = {}
        self._messages = []
        self._connected = False
        
        self.performance_log = 'logs/performance_log.csv'
        os.makedirs('logs', exist_ok=True)
        self._init_performance_log()
    
    def _init_performance_log(self):
        """Initialize performance log CSV"""
        if not os.path.exists(self.performance_log):
            with open(self.performance_log, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'event_type', 'channel', 'latency_ms', 'message_size'])
                
    def _lazy_connect(self):
        """Lazily connect to Redis to prevent import-time hangs."""
        if self._connected:
            return
        self._connected = True
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,
                socket_timeout=1,
                socket_connect_timeout=1
            )
            self.redis_client.ping()
            self.use_redis = True
        except Exception:
            self.use_redis = False
            self.redis_client = None
    
    def publish(self, channel, message):
        """Publish message to channel"""
        self._lazy_connect()
        start_time = time.time()
        
        if isinstance(message, dict):
            message = json.dumps(message)
        
        if self.use_redis:
            self.redis_client.publish(channel, message)
        else:
            # Fallback: store in memory
            if channel not in self._subscribers:
                self._subscribers[channel] = []
            self._messages.append((channel, message))
        
        # Log performance
        latency = (time.time() - start_time) * 1000
        self._log_performance('publish', channel, latency, len(message))
    
    def subscribe(self, channel, callback):
        """Subscribe to channel with callback"""
        self._lazy_connect()
        if self.use_redis:
            def redis_listener():
                pubsub = self.redis_client.pubsub()
                pubsub.subscribe(channel)
                for message in pubsub.listen():
                    if message['type'] == 'message':
                        start_time = time.time()
                        try:
                            data = json.loads(message['data'])
                        except:
                            data = message['data']
                        callback(data)
                        latency = (time.time() - start_time) * 1000
                        self._log_performance('subscribe', channel, latency, len(str(data)))
            
            thread = threading.Thread(target=redis_listener, daemon=True)
            thread.start()
        else:
            # Fallback: in-memory subscription
            if channel not in self._subscribers:
                self._subscribers[channel] = []
            self._subscribers[channel].append(callback)
            
            # Process existing messages for this channel
            def process_messages():
                pending = list(self._messages)
                for i, (msg_channel, message) in enumerate(pending):
                    if msg_channel == channel:
                        start_time = time.time()
                        try:
                            data = json.loads(message)
                        except:
                            data = message
                        callback(data)
                        latency = (time.time() - start_time) * 1000
                        self._log_performance('subscribe', channel, latency, len(str(data)))
                        if i < len(self._messages):
                            self._messages.pop(i)
            
            thread = threading.Thread(target=process_messages, daemon=True)
            thread.start()
    
    def emit(self, event_type, data):
        """Emit event (alias for publish)"""
        self.publish(event_type, data)
    
    def _log_performance(self, event_type, channel, latency_ms, message_size):
        """Log performance metrics"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.performance_log, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, event_type, channel, f'{latency_ms:.2f}', message_size])

# Global event bus instance
event_bus = EventBus()