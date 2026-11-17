#!/usr/bin/env python3
"""
Metrics Collector
Centralized metrics collection for observability
"""

import os
import csv
import datetime
import time
from typing import Dict, Any, List
from control_plane.core.env_config import EnvironmentConfig

class MetricsCollector:
    """Centralized metrics collection system."""
    
    def __init__(self, env='dev'):
        self.env = env
        self.env_config = EnvironmentConfig(env)
        self.metrics_dir = self.env_config.get_log_path("metrics")
        
        # Ensure metrics directory exists
        os.makedirs(self.metrics_dir, exist_ok=True)
        
        # Initialize metric files
        self._initialize_metrics()
        
        print(f"Initialized Metrics Collector for {env.upper()} environment")
    
    def _initialize_metrics(self):
        """Initialize all metric CSV files."""
        
        # Uptime metrics
        uptime_file = os.path.join(self.metrics_dir, "uptime_metrics.csv")
        if not os.path.exists(uptime_file):
            with open(uptime_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'service_name', 'status', 'uptime_seconds',
                    'downtime_seconds', 'availability_percent', 'environment'
                ])
        
        # Latency metrics
        latency_file = os.path.join(self.metrics_dir, "latency_metrics.csv")
        if not os.path.exists(latency_file):
            with open(latency_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'service_name', 'operation', 'latency_ms',
                    'p50_ms', 'p95_ms', 'p99_ms', 'environment'
                ])
        
        # Queue depth metrics
        queue_file = os.path.join(self.metrics_dir, "queue_depth.csv")
        if not os.path.exists(queue_file):
            with open(queue_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'queue_name', 'depth', 'enqueue_rate',
                    'dequeue_rate', 'avg_wait_time_ms', 'environment'
                ])
        
        # Deploy success rate metrics
        deploy_file = os.path.join(self.metrics_dir, "deploy_success_rate.csv")
        if not os.path.exists(deploy_file):
            with open(deploy_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'total_deployments', 'successful_deployments',
                    'failed_deployments', 'success_rate_percent', 'avg_deploy_time_ms',
                    'environment'
                ])
        
        # Error metrics
        error_file = os.path.join(self.metrics_dir, "error_metrics.csv")
        if not os.path.exists(error_file):
            with open(error_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'service_name', 'error_type', 'error_count',
                    'error_rate_percent', 'severity', 'environment'
                ])
    
    def record_uptime_metric(self, service_name: str, status: str, 
                           uptime_seconds: float, downtime_seconds: float = 0):
        """Record uptime metrics for a service."""
        total_time = uptime_seconds + downtime_seconds
        availability = (uptime_seconds / total_time * 100) if total_time > 0 else 100
        
        uptime_file = os.path.join(self.metrics_dir, "uptime_metrics.csv")
        timestamp = datetime.datetime.now().isoformat()
        
        with open(uptime_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, service_name, status, round(uptime_seconds, 2),
                round(downtime_seconds, 2), round(availability, 2), self.env
            ])
    
    def record_latency_metric(self, service_name: str, operation: str, 
                            latency_ms: float, percentiles: Dict[str, float] = None):
        """Record latency metrics for a service operation."""
        if percentiles is None:
            percentiles = {'p50': latency_ms, 'p95': latency_ms, 'p99': latency_ms}
        
        latency_file = os.path.join(self.metrics_dir, "latency_metrics.csv")
        timestamp = datetime.datetime.now().isoformat()
        
        with open(latency_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, service_name, operation, round(latency_ms, 2),
                round(percentiles.get('p50', latency_ms), 2),
                round(percentiles.get('p95', latency_ms), 2),
                round(percentiles.get('p99', latency_ms), 2),
                self.env
            ])
    
    def record_queue_metric(self, queue_name: str, depth: int, 
                          enqueue_rate: float = 0, dequeue_rate: float = 0,
                          avg_wait_time_ms: float = 0):
        """Record queue depth and performance metrics."""
        queue_file = os.path.join(self.metrics_dir, "queue_depth.csv")
        timestamp = datetime.datetime.now().isoformat()
        
        with open(queue_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, queue_name, depth, round(enqueue_rate, 2),
                round(dequeue_rate, 2), round(avg_wait_time_ms, 2), self.env
            ])
    
    def record_deploy_success_rate(self, total: int, successful: int, 
                                 failed: int, avg_deploy_time_ms: float):
        """Record deployment success rate metrics."""
        success_rate = (successful / total * 100) if total > 0 else 0
        
        deploy_file = os.path.join(self.metrics_dir, "deploy_success_rate.csv")
        timestamp = datetime.datetime.now().isoformat()
        
        with open(deploy_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, total, successful, failed, round(success_rate, 2),
                round(avg_deploy_time_ms, 2), self.env
            ])
    
    def record_error_metric(self, service_name: str, error_type: str, 
                          error_count: int, total_requests: int = 1,
                          severity: str = 'medium'):
        """Record error metrics for a service."""
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
        
        error_file = os.path.join(self.metrics_dir, "error_metrics.csv")
        timestamp = datetime.datetime.now().isoformat()
        
        with open(error_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, service_name, error_type, error_count,
                round(error_rate, 2), severity, self.env
            ])
    
    def record_deploy_metric(self, service_name: str, status: str, response_time: float):
        """Record deployment metric."""
        self.record_latency_metric(service_name, 'deploy', response_time)
        if status == 'success':
            self.record_deploy_success_rate(1, 1, 0, response_time)
        else:
            self.record_deploy_success_rate(1, 0, 1, response_time)
    
    def record_scale_metric(self, service_name: str, direction: str, worker_count: int):
        """Record scaling metric."""
        self.record_latency_metric(service_name, f'scale_{direction}', 0)
        # Record as queue metric to track worker count
        self.record_queue_metric(f'{service_name}_workers', worker_count)
    
    def record_performance_metric(self, service_name: str, response_time: float, success: bool):
        """Record general performance metric."""
        self.record_latency_metric(service_name, 'performance', response_time)
        if not success:
            self.record_error_metric(service_name, 'performance_failure', 1)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        summary = {
            'environment': self.env,
            'metrics_collected': 0,
            'services_monitored': set(),
            'last_updated': datetime.datetime.now().isoformat()
        }
        
        # Count metrics from each file
        metric_files = [
            'uptime_metrics.csv',
            'latency_metrics.csv', 
            'queue_depth.csv',
            'deploy_success_rate.csv',
            'error_metrics.csv'
        ]
        
        for metric_file in metric_files:
            file_path = os.path.join(self.metrics_dir, metric_file)
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    summary['metrics_collected'] += len(rows) - 1  # Exclude header
                    
                    # Extract service names (assuming service_name is in column 1)
                    if len(rows) > 1:
                        for row in rows[1:]:
                            if len(row) > 1:
                                summary['services_monitored'].add(row[1])
        
        summary['services_monitored'] = list(summary['services_monitored'])
        return summary

# Global metrics collector instances
_metrics_collectors = {}

def get_metrics_collector(env='dev') -> MetricsCollector:
    """Get or create metrics collector for environment."""
    global _metrics_collectors
    if env not in _metrics_collectors:
        _metrics_collectors[env] = MetricsCollector(env)
    return _metrics_collectors[env]