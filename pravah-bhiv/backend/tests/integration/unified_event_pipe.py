#!/usr/bin/env python3
"""
Unified Event Pipe
Single interface for Ritesh's automation layer - no changes required on his side
"""

import json
import time
import threading
import os
from typing import Dict, List, Any, Callable, Optional
from integration.api_adapter import get_api_adapter
from integration.event_schema import StandardEvent, EventValidator
from security.auth import verify_token

class UnifiedEventPipe:
    """Unified event pipe for external automation systems."""
    
    def __init__(self, environments: List[str] = None):
        if environments is None:
            environments = ['dev', 'stage', 'prod']
        
        self.environments = environments
        self.adapters = {env: get_api_adapter(env) for env in environments}
        self.subscribers = []
        self.running = False
        self.poll_interval = 5  # seconds
        self.last_event_counts = {env: 0 for env in environments}
        
    def _check_auth(self, token: str = None):
        """Check authentication token."""
        token = token or os.getenv('API_TOKEN')
        if not token:
            # Allow access if no token configured (dev mode)
            return True
        return verify_token(token)
    
    def get_latest_events(self, limit: int = 100, env: str = None, token: str = None) -> List[Dict[str, Any]]:
        """Get latest events from all or specific environment."""
        if not self._check_auth(token):
            raise PermissionError('Invalid or missing authentication token')
        if env:
            if env in self.adapters:
                return self.adapters[env].get_unified_event_stream(limit)
            else:
                return []
        
        # Collect from all environments
        all_events = []
        for adapter in self.adapters.values():
            events = adapter.get_unified_event_stream(limit // len(self.adapters))
            all_events.extend(events)
        
        # Sort by timestamp and return latest
        try:
            all_events.sort(key=lambda x: x["timestamp"])
        except:
            pass
        
        return all_events[-limit:]
    
    def get_system_health(self, token: str = None) -> Dict[str, Any]:
        """Get overall system health across all environments."""
        if not self._check_auth(token):
            raise PermissionError('Invalid or missing authentication token')
        health_summary = {
            "overall_status": "healthy",
            "environments": {},
            "timestamp": time.time(),
            "summary": {
                "total_environments": len(self.environments),
                "healthy_environments": 0,
                "warning_environments": 0,
                "critical_environments": 0
            }
        }
        
        for env in self.environments:
            env_status = self.adapters[env].get_system_status()
            health_summary["environments"][env] = env_status
            
            # Count environment statuses
            status = env_status["status"]
            if status == "healthy":
                health_summary["summary"]["healthy_environments"] += 1
            elif status == "warning":
                health_summary["summary"]["warning_environments"] += 1
            elif status == "critical":
                health_summary["summary"]["critical_environments"] += 1
        
        # Determine overall status
        if health_summary["summary"]["critical_environments"] > 0:
            health_summary["overall_status"] = "critical"
        elif health_summary["summary"]["warning_environments"] > 0:
            health_summary["overall_status"] = "warning"
        else:
            health_summary["overall_status"] = "healthy"
        
        return health_summary
    
    def get_learning_metrics(self, token: str = None) -> Dict[str, Any]:
        """Get aggregated learning metrics for ML/RL systems."""
        if not self._check_auth(token):
            raise PermissionError('Invalid or missing authentication token')
        learning_data = {
            "timestamp": time.time(),
            "environments": {},
            "aggregated": {
                "avg_deployment_success_rate": 0.0,
                "avg_healing_effectiveness": 0.0,
                "avg_system_stability": 0.0,
                "total_events_last_hour": 0
            }
        }
        
        success_rates = []
        healing_rates = []
        stability_scores = []
        
        for env in self.environments:
            env_data = self.adapters[env].get_learning_data()
            learning_data["environments"][env] = env_data
            
            success_rates.append(env_data["deployment_success_rate"])
            healing_rates.append(env_data["healing_effectiveness"])
            stability_scores.append(env_data["system_stability"])
        
        # Calculate aggregated metrics
        if success_rates:
            learning_data["aggregated"]["avg_deployment_success_rate"] = sum(success_rates) / len(success_rates)
        if healing_rates:
            learning_data["aggregated"]["avg_healing_effectiveness"] = sum(healing_rates) / len(healing_rates)
        if stability_scores:
            learning_data["aggregated"]["avg_system_stability"] = sum(stability_scores) / len(stability_scores)
        
        return learning_data
    
    def subscribe_to_events(self, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe to real-time event notifications."""
        self.subscribers.append(callback)
    
    def start_event_monitoring(self):
        """Start background event monitoring for subscribers."""
        if self.running:
            return
        
        self.running = True
        monitor_thread = threading.Thread(target=self._monitor_events, daemon=True)
        monitor_thread.start()
        print("🔄 Event monitoring started")
    
    def stop_event_monitoring(self):
        """Stop background event monitoring."""
        self.running = False
        print("🛑 Event monitoring stopped")
    
    def _monitor_events(self):
        """Background thread to monitor for new events."""
        while self.running:
            try:
                for env in self.environments:
                    # Check for new events
                    current_events = self.adapters[env].get_unified_event_stream(10)
                    current_count = len(current_events)
                    
                    if current_count > self.last_event_counts[env]:
                        # New events detected
                        new_events = current_events[self.last_event_counts[env]:]
                        
                        for event in new_events:
                            # Validate event
                            if EventValidator.validate(event):
                                # Notify subscribers
                                for callback in self.subscribers:
                                    try:
                                        callback(event)
                                    except Exception as e:
                                        print(f"Subscriber callback error: {e}")
                        
                        self.last_event_counts[env] = current_count
                
                time.sleep(self.poll_interval)
                
            except Exception as e:
                print(f"Event monitoring error: {e}")
                time.sleep(self.poll_interval)
    
    def export_events_for_ritesh(self, output_file: str = "unified_events.json", 
                                limit: int = 1000) -> str:
        """Export events in format ready for Ritesh's consumption."""
        
        # Get all events
        all_events = self.get_latest_events(limit)
        
        # Validate and sanitize events
        clean_events = []
        for event in all_events:
            if EventValidator.validate(event):
                clean_event = EventValidator.sanitize(event)
                clean_events.append(clean_event)
        
        # Create export package
        export_data = {
            "metadata": {
                "export_timestamp": time.time(),
                "total_events": len(clean_events),
                "environments": self.environments,
                "schema_version": "1.0"
            },
            "system_health": self.get_system_health(),
            "learning_metrics": self.get_learning_metrics(),
            "events": clean_events
        }
        
        try:
            with open(output_file, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            print(f"✅ Events exported for Ritesh: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"❌ Export failed: {e}")
            return ""
    
    def get_api_summary(self) -> Dict[str, Any]:
        """Get API summary for integration documentation."""
        return {
            "available_methods": [
                "get_latest_events(limit, env)",
                "get_system_health()",
                "get_learning_metrics()",
                "subscribe_to_events(callback)",
                "export_events_for_ritesh(output_file)"
            ],
            "event_schema": {
                "required_fields": ["event", "env", "status", "latency", "timestamp"],
                "event_types": ["deployment", "healing", "issue_detected", "metric_*"],
                "environments": self.environments,
                "status_values": ["success", "failure", "warning", "detected", "recorded"]
            },
            "environments": self.environments,
            "real_time_monitoring": self.running
        }

# Global unified event pipe instance
_unified_pipe = None

def get_unified_pipe(environments: List[str] = None) -> UnifiedEventPipe:
    """Get or create unified event pipe."""
    global _unified_pipe
    if _unified_pipe is None:
        _unified_pipe = UnifiedEventPipe(environments)
    return _unified_pipe

# Convenience functions for Ritesh's integration
def get_events(limit: int = 100, env: str = None) -> List[Dict[str, Any]]:
    """Simple function to get latest events."""
    pipe = get_unified_pipe()
    return pipe.get_latest_events(limit, env)

def get_health() -> Dict[str, Any]:
    """Simple function to get system health."""
    pipe = get_unified_pipe()
    return pipe.get_system_health()

def get_metrics() -> Dict[str, Any]:
    """Simple function to get learning metrics."""
    pipe = get_unified_pipe()
    return pipe.get_learning_metrics()

def export_for_automation(filename: str = "automation_data.json") -> str:
    """Simple function to export data for automation systems."""
    pipe = get_unified_pipe()
    return pipe.export_events_for_ritesh(filename)