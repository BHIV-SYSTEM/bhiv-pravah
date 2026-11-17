#!/usr/bin/env python3
"""
Perception Adapters - Individual perception sources
Adapters for different perception sources (runtime events, health, onboarding).
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
# from core.perception import Perception, PerceptionType, PerceptionPriority
from control_plane.core.perception import Perception

class PerceptionAdapter:
    """Base class for perception adapters."""
    
    def perceive(self) -> List[Perception]:
        """Perceive from this source.
        
        Returns:
            List of perceptions
        """
        raise NotImplementedError("Subclasses must implement perceive()")


class RuntimeEventAdapter(PerceptionAdapter):
    """Adapter for runtime events from the event bus."""
    
    def __init__(self, event_bus):
        """Initialize runtime event adapter.
        
        Args:
            event_bus: Event bus instance to read from
        """
        self.event_bus = event_bus
        self.last_event_time = None
    
    def perceive(self) -> List[Perception]:
        """Perceive runtime events from the event bus.
        
        Returns:
            List of runtime event perceptions
        """
        perceptions = []
        
        try:
            # Get recent events from event bus
            events = self.event_bus.get_recent_events(limit=5)
            
            for event in events:
                # Determine priority based on event type
                priority = self._determine_priority(event)
                
                perception = Perception(
                    type=PerceptionType.RUNTIME_EVENT.value,
                    source="redis_event_bus",
                    timestamp=event.get('timestamp', datetime.utcnow().isoformat()),
                    data=event,
                    priority=priority
                )
                perceptions.append(perception)
        
        except Exception as e:
            # If event bus unavailable, return empty list
            pass
        
        return perceptions
    
    def _determine_priority(self, event: Dict[str, Any]) -> int:
        """Determine priority based on event type.
        
        Args:
            event: Event dictionary
            
        Returns:
            Priority level (1-10)
        """
        event_type = event.get('type', '').lower()
        
        # Critical events
        if any(word in event_type for word in ['failure', 'error', 'crash', 'down']):
            return PerceptionPriority.CRITICAL.value
        
        # High priority events
        if any(word in event_type for word in ['deploy', 'rollback', 'alert']):
            return PerceptionPriority.HIGH.value
        
        # Medium priority events
        if any(word in event_type for word in ['scale', 'update', 'config']):
            return PerceptionPriority.MEDIUM.value
        
        # Default to low priority
        return PerceptionPriority.LOW.value


class HealthSignalAdapter(PerceptionAdapter):
    """Adapter for health signals and system metrics."""
    
    def __init__(self, uptime_monitor=None):
        """Initialize health signal adapter.
        
        Args:
            uptime_monitor: UptimeMonitor instance (optional)
        """
        self.uptime_monitor = uptime_monitor
    
    def perceive(self) -> List[Perception]:
        """Perceive health signals from monitoring systems.
        
        Returns:
            List of health signal perceptions
        """
        perceptions = []
        
        # Check if uptime monitor is available
        if self.uptime_monitor:
            try:
                # Get app health status
                health_data = self._get_health_status()
                
                if health_data:
                    priority = self._determine_health_priority(health_data)
                    
                    perception = Perception(
                        type=PerceptionType.HEALTH_SIGNAL.value,
                        source="uptime_monitor",
                        timestamp=datetime.utcnow().isoformat(),
                        data=health_data,
                        priority=priority
                    )
                    perceptions.append(perception)
            
            except Exception as e:
                pass
        
        return perceptions
    
    def _get_health_status(self) -> Optional[Dict[str, Any]]:
        """Get current health status from monitor.
        
        Returns:
            Health status dictionary or None
        """
        if not self.uptime_monitor:
            return None
        
        try:
            # Try to get app health from uptime monitor
            # This is a placeholder - adapt to actual uptime monitor API
            return {
                "status": "healthy",
                "cpu": 45.2,
                "memory": 62.1,
                "error_rate": 0.01,
                "timestamp": datetime.utcnow().isoformat()
            }
        except:
            return None
    
    def _determine_health_priority(self, health_data: Dict[str, Any]) -> int:
        """Determine priority based on health metrics.
        
        Args:
            health_data: Health metrics
            
        Returns:
            Priority level (1-10)
        """
        status = health_data.get('status', 'unknown').lower()
        error_rate = health_data.get('error_rate', 0)
        cpu = health_data.get('cpu', 0)
        memory = health_data.get('memory', 0)
        
        # Critical health issues
        if status in ['critical', 'down', 'failing']:
            return PerceptionPriority.CRITICAL.value
        
        # Medium priority if status is degraded
        if status in ['degraded', 'warning']:
            return PerceptionPriority.MEDIUM.value
        
        # Low priority for healthy systems
        return PerceptionPriority.INFO.value


class OnboardingInputAdapter(PerceptionAdapter):
    """Adapter for onboarding input from file-based perception.
    
    Watches onboarding_requests.jsonl for new app registration requests.
    Each line: {"app_id": "service-name", "description": "service description"}
    """
    
    def __init__(self, watch_file: str = "data/onboarding_requests.jsonl"):
        """Initialize onboarding file watcher.
        
        Args:
            watch_file: Path to JSONL file to watch for onboarding requests
        """
        self.watch_file = watch_file
        self.processed_lines = set()  # Track processed line numbers
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Ensure the watch file exists."""
        from pathlib import Path
        file_path = Path(self.watch_file)
        if not file_path.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.touch()
    
    def perceive(self) -> List[Perception]:
        """Perceive onboarding requests from file.
        
        Reads JSONL file, detects new (unprocessed) entries, and returns perceptions.
        
        Returns:
            List of onboarding perceptions
        """
        import json
        from pathlib import Path
        
        perceptions = []
        
        try:
            file_path = Path(self.watch_file)
            
            if not file_path.exists():
                return perceptions
            
            # Read all lines
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Process new lines only
            for line_num, line in enumerate(lines):
                if line_num in self.processed_lines:
                    continue
                
                line = line.strip()
                if not line:
                    self.processed_lines.add(line_num)
                    continue
                
                try:
                    # Parse JSONL entry
                    request_data = json.loads(line)
                    
                    # Validate required fields
                    if 'app_id' not in request_data:
                        print(f"Warning: Onboarding request missing 'app_id': {line}")
                        self.processed_lines.add(line_num)
                        continue
                    
                    # Create perception
                    perception = Perception(
                        type=PerceptionType.ONBOARDING_INPUT.value,
                        source="file_watcher",
                        timestamp=datetime.now().isoformat(),
                        data=request_data,
                        priority=PerceptionPriority.HIGH.value
                    )
                    
                    perceptions.append(perception)
                    self.processed_lines.add(line_num)
                
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON in onboarding file line {line_num}: {e}")
                    self.processed_lines.add(line_num)
        
        except Exception as e:
            print(f"Error reading onboarding file: {e}")
        
        return perceptions
    
    def add_onboarding_request(self, app_data: Dict[str, Any]):
        """Add an onboarding request to the file.
        
        This method allows programmatic addition for testing/compatibility.
        
        Args:
            app_data: Application onboarding data
        """
        import json
        from pathlib import Path
        
        file_path = Path(self.watch_file)
        
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(app_data) + '\n')
    
    def get_processed_count(self) -> int:
        """Get count of processed onboarding requests.
        
        Returns:
            Number of requests processed
        """
        return len(self.processed_lines)
    
    def reset_processed(self):
        """Reset processed tracking (for testing)."""
        self.processed_lines.clear()


class SystemAlertAdapter(PerceptionAdapter):
    """Adapter for system-level alerts."""
    
    def __init__(self):
        """Initialize system alert adapter."""
        self.alerts = []
    
    def add_alert(self, alert_type: str, message: str, severity: str = "medium"):
        """Add a system alert.
        
        Args:
            alert_type: Type of alert
            message: Alert message
            severity: Severity level (critical/high/medium/low)
        """
        self.alerts.append({
            'type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def perceive(self) -> List[Perception]:
        """Perceive system alerts.
        
        Returns:
            List of alert perceptions
        """
        perceptions = []
        
        # Process all pending alerts
        while self.alerts:
            alert = self.alerts.pop(0)
            
            # Map severity to priority
            priority_map = {
                'critical': PerceptionPriority.CRITICAL.value,
                'high': PerceptionPriority.HIGH.value,
                'medium': PerceptionPriority.MEDIUM.value,
                'low': PerceptionPriority.LOW.value
            }
            priority = priority_map.get(alert.get('severity', 'medium'), PerceptionPriority.MEDIUM.value)
            
            perception = Perception(
                type=PerceptionType.SYSTEM_ALERT.value,
                source="system",
                timestamp=alert['timestamp'],
                data=alert,
                priority=priority
            )
            perceptions.append(perception)
        
        return perceptions
