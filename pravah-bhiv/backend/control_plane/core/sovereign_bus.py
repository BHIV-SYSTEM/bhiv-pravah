import json
import datetime
import os
from typing import Dict, List, Callable, Any
from .event_bus import event_bus

class SovereignBus:
    """Event bus with Redis pub/sub and file-based persistence."""
    
    def __init__(self, log_file="bus_events.json"):
        self.listeners: Dict[str, List[Callable]] = {}
        self.log_file = log_file
        self.message_log: List[Dict] = self._load_messages()
        self.event_bus = event_bus
    
    def _load_messages(self):
        """Load existing messages from file."""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return []
    
    def _save_messages(self):
        """Save messages to file."""
        try:
            with open(self.log_file, 'w') as f:
                json.dump(self.message_log[-100:], f, indent=2)  # Keep last 100
        except Exception as e:
            print(f"Bus save error: {e}")
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to event type via Redis and local."""
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)
        
        # Subscribe via Redis
        self.event_bus.subscribe(event_type, callback)
    
    def publish(self, event_type: str, data: Any = None):
        """Publish event via Redis and save to file."""
        message = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        }
        self.message_log.append(message)
        self._save_messages()
        
        # Publish via Redis
        self.event_bus.publish(event_type, message)
        
        # Notify local subscribers
        if event_type in self.listeners:
            for callback in self.listeners[event_type]:
                try:
                    callback(message)
                except Exception as e:
                    print(f"Bus error: {e}")
    
    def get_messages(self, event_type: str = None) -> List[Dict]:
        """Get message history."""
        self.message_log = self._load_messages()  # Refresh from file
        if event_type:
            return [msg for msg in self.message_log if msg["event_type"] == event_type]
        return self.message_log

# Global bus instance
bus = SovereignBus()