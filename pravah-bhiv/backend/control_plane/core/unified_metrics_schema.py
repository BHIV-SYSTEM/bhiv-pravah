#!/usr/bin/env python3
"""Unified Metrics Schema for Normalization"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
import time

@dataclass
class UnifiedMetric:
    """Standardized metric format across all environments."""
    
    metric_type: str        # latency, uptime, queue_depth, deploy_success, error_rate
    environment: str        # dev, stage, prod
    component: str          # deploy_agent, issue_detector, auto_heal, etc.
    value: float           # metric value
    unit: str              # ms, percentage, count, etc.
    timestamp: float       # unix timestamp
    tags: Dict[str, str]   # additional metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'metric_type': self.metric_type,
            'environment': self.environment,
            'component': self.component,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp,
            'tags': self.tags
        }
    
    @classmethod
    def from_legacy(cls, legacy_data: Dict[str, Any], metric_type: str, env: str) -> 'UnifiedMetric':
        """Convert legacy metric format to unified schema."""
        return cls(
            metric_type=metric_type,
            environment=env,
            component=legacy_data.get('component', 'unknown'),
            value=float(legacy_data.get('value', 0)),
            unit=legacy_data.get('unit', 'count'),
            timestamp=legacy_data.get('timestamp', time.time()),
            tags=legacy_data.get('tags', {})
        )

class MetricsNormalizer:
    """Normalizes metrics from different sources into unified schema."""
    
    @staticmethod
    def normalize_latency_metric(component: str, operation: str, latency_ms: float, env: str) -> UnifiedMetric:
        """Normalize latency metrics."""
        return UnifiedMetric(
            metric_type='latency',
            environment=env,
            component=component,
            value=latency_ms,
            unit='milliseconds',
            timestamp=time.time(),
            tags={'operation': operation}
        )
    
    @staticmethod
    def normalize_uptime_metric(component: str, uptime_pct: float, env: str) -> UnifiedMetric:
        """Normalize uptime metrics."""
        return UnifiedMetric(
            metric_type='uptime',
            environment=env,
            component=component,
            value=uptime_pct,
            unit='percentage',
            timestamp=time.time(),
            tags={'status': 'healthy' if uptime_pct > 95 else 'degraded'}
        )
    
    @staticmethod
    def normalize_queue_metric(queue_name: str, depth: int, workers: int, env: str) -> UnifiedMetric:
        """Normalize queue depth metrics."""
        return UnifiedMetric(
            metric_type='queue_depth',
            environment=env,
            component='queue_manager',
            value=float(depth),
            unit='count',
            timestamp=time.time(),
            tags={'queue_name': queue_name, 'workers': str(workers)}
        )
    
    @staticmethod
    def normalize_deploy_success_metric(total: int, success: int, env: str) -> UnifiedMetric:
        """Normalize deployment success metrics."""
        success_rate = (success / total * 100) if total > 0 else 0
        return UnifiedMetric(
            metric_type='deploy_success',
            environment=env,
            component='deploy_agent',
            value=success_rate,
            unit='percentage',
            timestamp=time.time(),
            tags={'total_deployments': str(total), 'successful_deployments': str(success)}
        )