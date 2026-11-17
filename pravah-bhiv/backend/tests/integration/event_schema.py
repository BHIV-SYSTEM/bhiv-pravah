#!/usr/bin/env python3
"""
Standardized Event Schema
Defines the unified event format for automation agents
"""

import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class StandardEvent:
    """Standardized event schema for all system events."""
    
    event: str              # Event type: "deployment", "healing", "issue_detected", etc.
    env: str               # Environment: "dev", "stage", "prod"
    status: str            # Status: "success", "failure", "warning", "detected", etc.
    latency: float         # Latency in milliseconds (0 if not applicable)
    timestamp: str         # ISO format timestamp
    
    # Optional fields for specific event types
    dataset: Optional[str] = None
    action_type: Optional[str] = None
    worker_id: Optional[int] = None
    strategy: Optional[str] = None
    failure_type: Optional[str] = None
    reason: Optional[str] = None
    metric_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_deployment(cls, env: str, status: str, latency: float, 
                       dataset: str = "", action_type: str = "deploy", 
                       worker_id: int = 1) -> 'StandardEvent':
        """Create deployment event."""
        return cls(
            event="deployment",
            env=env,
            status=status,
            latency=latency,
            timestamp=datetime.datetime.now().isoformat(),
            dataset=dataset,
            action_type=action_type,
            worker_id=worker_id
        )
    
    @classmethod
    def from_healing(cls, env: str, status: str, latency: float, 
                    strategy: str = "unknown") -> 'StandardEvent':
        """Create healing event."""
        return cls(
            event="healing",
            env=env,
            status=status,
            latency=latency,
            timestamp=datetime.datetime.now().isoformat(),
            strategy=strategy
        )
    
    @classmethod
    def from_issue(cls, env: str, failure_type: str, 
                  reason: str = "") -> 'StandardEvent':
        """Create issue detection event."""
        return cls(
            event="issue_detected",
            env=env,
            status="detected",
            latency=0,
            timestamp=datetime.datetime.now().isoformat(),
            failure_type=failure_type,
            reason=reason
        )
    
    @classmethod
    def from_metric(cls, env: str, metric_type: str, 
                   metric_data: Dict[str, Any]) -> 'StandardEvent':
        """Create metric event."""
        return cls(
            event=f"metric_{metric_type}",
            env=env,
            status="recorded",
            latency=0,
            timestamp=datetime.datetime.now().isoformat(),
            metric_data=metric_data
        )

class EventValidator:
    """Validates events against the standard schema."""
    
    REQUIRED_FIELDS = ["event", "env", "status", "latency", "timestamp"]
    VALID_EVENTS = [
        "deployment", "healing", "issue_detected", "system_status",
        "metric_uptime", "metric_latency", "metric_queue", 
        "metric_deploy_success", "metric_error"
    ]
    VALID_ENVIRONMENTS = ["dev", "stage", "prod"]
    VALID_STATUSES = [
        "success", "failure", "warning", "detected", "recorded", 
        "healthy", "critical", "unknown"
    ]
    
    @classmethod
    def validate(cls, event_dict: Dict[str, Any]) -> bool:
        """Validate event dictionary against schema."""
        
        # Check required fields
        for field in cls.REQUIRED_FIELDS:
            if field not in event_dict:
                return False
        
        # Validate event type
        if event_dict["event"] not in cls.VALID_EVENTS:
            return False
        
        # Validate environment
        if event_dict["env"] not in cls.VALID_ENVIRONMENTS:
            return False
        
        # Validate status
        if event_dict["status"] not in cls.VALID_STATUSES:
            return False
        
        # Validate latency is numeric
        try:
            float(event_dict["latency"])
        except (ValueError, TypeError):
            return False
        
        # Validate timestamp format
        try:
            datetime.datetime.fromisoformat(event_dict["timestamp"].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return False
        
        return True
    
    @classmethod
    def sanitize(cls, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize and normalize event dictionary."""
        sanitized = {}
        
        # Copy required fields
        for field in cls.REQUIRED_FIELDS:
            if field in event_dict:
                sanitized[field] = event_dict[field]
        
        # Normalize values
        if "latency" in sanitized:
            try:
                sanitized["latency"] = float(sanitized["latency"])
            except:
                sanitized["latency"] = 0.0
        
        if "env" in sanitized:
            sanitized["env"] = str(sanitized["env"]).lower()
        
        if "status" in sanitized:
            sanitized["status"] = str(sanitized["status"]).lower()
        
        # Copy optional fields
        optional_fields = [
            "dataset", "action_type", "worker_id", "strategy", 
            "failure_type", "reason", "metric_data"
        ]
        
        for field in optional_fields:
            if field in event_dict and event_dict[field] is not None:
                sanitized[field] = event_dict[field]
        
        return sanitized