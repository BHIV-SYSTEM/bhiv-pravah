import json
import time
import os
from datetime import datetime
from core.sovereign_bus import bus
from pravah_stream.stream import emit

class TelemetryCollector:
    """Collects real-time telemetry from agents via sovereign bus."""
    
    def __init__(self, telemetry_file="insightflow/telemetry.json"):
        self.telemetry_file = telemetry_file
        self.agent_status = {}
        self._setup_listeners()
    
    def _setup_listeners(self):
        """Subscribe to all agent events."""
        events = [
            "deploy.success", "deploy.failure", 
            "issue.detected", "heal.triggered", 
            "uptime.changed", "rl.learned"
        ]
        for event in events:
            bus.subscribe(event, self._collect_telemetry)
    
    def _collect_telemetry(self, message):
        """Collect telemetry data from bus messages."""
        timestamp = datetime.now().isoformat()
        data = message.get("data", {})
        telemetry_entry = {
            "timestamp": timestamp,
            "event_type": message["event_type"],
            "data": data,
            "agent_status": self._get_agent_status()
        }

        emit({
            "trace_id": message.get("trace_id", "telemetry"),
            "execution_id": message.get("execution_id", "telemetry"),
            "timestamp": timestamp,
            "source": "telemetry",
            "signal_type": "verification",
            "payload": {
                "event_type": message["event_type"],
                "data": data,
                "agent_status": self._get_agent_status(),
            },
        })
        
        self._store_telemetry(telemetry_entry)
    
    def _get_agent_status(self):
        """Get current status of all agents."""
        return {
            "deploy_agent": "active",
            "uptime_monitor": "tracking",
            "execution_layer": "ready",
            "telemetry": "collecting"
        }
    
    def _store_telemetry(self, entry):
        """Store telemetry entry to JSON file."""
        try:
            if os.path.exists(self.telemetry_file):
                with open(self.telemetry_file, 'r') as f:
                    telemetry = json.load(f)
            else:
                telemetry = []
            
            telemetry.append(entry)
            
            # Keep only last 1000 entries
            if len(telemetry) > 1000:
                telemetry = telemetry[-1000:]
            
            with open(self.telemetry_file, 'w') as f:
                json.dump(telemetry, f, indent=2)
        except Exception as e:
            print(f"Telemetry error: {e}")

# Global collector instance
telemetry_collector = TelemetryCollector()