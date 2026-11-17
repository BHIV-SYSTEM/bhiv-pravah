#!/usr/bin/env python3
"""
Metrics Aggregator
Aggregates metrics data for dashboard visualization
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from core.env_config import EnvironmentConfig

class MetricsAggregator:
    """Aggregates metrics data for dashboard consumption."""
    
    def __init__(self, environments=['dev', 'stage', 'prod']):
        self.environments = environments
        self.env_configs = {env: EnvironmentConfig(env) for env in environments}
    
    def get_environment_health(self) -> Dict[str, Any]:
        """Get health status for all environments."""
        health_data = {}
        
        for env in self.environments:
            env_config = self.env_configs[env]
            metrics_dir = env_config.get_log_path("metrics")
            
            # Initialize environment health
            health_data[env] = {
                'status': 'unknown',
                'uptime_percent': 0,
                'avg_latency_ms': 0,
                'error_rate': 0,
                'last_deployment': 'never',
                'services_count': 0
            }
            
            # Read uptime metrics
            uptime_file = os.path.join(metrics_dir, "uptime_metrics.csv")
            if os.path.exists(uptime_file):
                try:
                    df = pd.read_csv(uptime_file)
                    if not df.empty:
                        latest_uptime = df.iloc[-1]
                        health_data[env]['uptime_percent'] = latest_uptime.get('availability_percent', 0)
                        health_data[env]['services_count'] = df['service_name'].nunique()
                        
                        # Determine status based on uptime
                        uptime = health_data[env]['uptime_percent']
                        if uptime >= 99:
                            health_data[env]['status'] = 'healthy'
                        elif uptime >= 95:
                            health_data[env]['status'] = 'warning'
                        else:
                            health_data[env]['status'] = 'critical'
                except Exception as e:
                    print(f"Error reading uptime metrics for {env}: {e}")
            
            # Read latency metrics
            latency_file = os.path.join(metrics_dir, "latency_metrics.csv")
            if os.path.exists(latency_file):
                try:
                    df = pd.read_csv(latency_file)
                    if not df.empty:
                        health_data[env]['avg_latency_ms'] = df['latency_ms'].mean()
                except Exception as e:
                    print(f"Error reading latency metrics for {env}: {e}")
            
            # Read error metrics
            error_file = os.path.join(metrics_dir, "error_metrics.csv")
            if os.path.exists(error_file):
                try:
                    df = pd.read_csv(error_file)
                    if not df.empty:
                        health_data[env]['error_rate'] = df['error_rate_percent'].mean()
                except Exception as e:
                    print(f"Error reading error metrics for {env}: {e}")
            
            # Read deployment data
            deploy_file = env_config.get_log_path("deployment_log.csv")
            if os.path.exists(deploy_file):
                try:
                    df = pd.read_csv(deploy_file)
                    if not df.empty:
                        health_data[env]['last_deployment'] = df.iloc[-1]['timestamp']
                except Exception as e:
                    print(f"Error reading deployment log for {env}: {e}")
        
        return health_data
    
    def get_scaling_activity(self) -> Dict[str, Any]:
        """Get scaling activity data across environments."""
        scaling_data = {
            'environments': [],
            'worker_counts': [],
            'queue_depths': [],
            'throughput': []
        }
        
        for env in self.environments:
            env_config = self.env_configs[env]
            
            # Read throughput data
            throughput_file = env_config.get_log_path("performance/throughput_log.csv")
            if os.path.exists(throughput_file):
                try:
                    df = pd.read_csv(throughput_file)
                    if not df.empty:
                        latest = df.iloc[-1]
                        scaling_data['environments'].append(env)
                        scaling_data['worker_counts'].append(latest.get('total_workers', 0))
                        scaling_data['queue_depths'].append(latest.get('queue_size', 0))
                        scaling_data['throughput'].append(latest.get('requests_per_second', 0))
                except Exception as e:
                    print(f"Error reading throughput data for {env}: {e}")
        
        return scaling_data
    
    def get_deployment_throughput(self, hours=24) -> Dict[str, Any]:
        """Get deployment throughput data for the last N hours."""
        throughput_data = {
            'timestamps': [],
            'environments': {},
            'total_deployments': 0,
            'success_rate': 0
        }
        
        # Initialize environment data
        for env in self.environments:
            throughput_data['environments'][env] = {
                'deployments': [],
                'success_rate': [],
                'avg_response_time': []
            }
        
        for env in self.environments:
            env_config = self.env_configs[env]
            
            # Read deployment logs
            deploy_file = env_config.get_log_path("deployment_log.csv")
            if os.path.exists(deploy_file):
                try:
                    df = pd.read_csv(deploy_file)
                    if not df.empty:
                        # Convert timestamp to datetime
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        
                        # Filter last N hours
                        cutoff_time = pd.Timestamp.now() - pd.Timedelta(hours=hours)
                        recent_df = df[df['timestamp'] >= cutoff_time]
                        
                        if not recent_df.empty:
                            # Group by hour
                            recent_df['hour'] = recent_df['timestamp'].dt.floor('H')
                            hourly_stats = recent_df.groupby('hour').agg({
                                'status': ['count', lambda x: (x == 'success').sum()],
                                'response_time_ms': 'mean'
                            }).reset_index()
                            
                            # Flatten column names
                            hourly_stats.columns = ['hour', 'total', 'successful', 'avg_time']
                            hourly_stats['success_rate'] = (hourly_stats['successful'] / hourly_stats['total'] * 100)
                            
                            # Store data
                            throughput_data['environments'][env]['deployments'] = hourly_stats['total'].tolist()
                            throughput_data['environments'][env]['success_rate'] = hourly_stats['success_rate'].tolist()
                            throughput_data['environments'][env]['avg_response_time'] = hourly_stats['avg_time'].tolist()
                            
                            # Update timestamps (use first environment's timestamps)
                            if not throughput_data['timestamps']:
                                throughput_data['timestamps'] = hourly_stats['hour'].dt.strftime('%H:%M').tolist()
                
                except Exception as e:
                    print(f"Error processing deployment throughput for {env}: {e}")
        
        return throughput_data
    
    def get_queue_depth_over_time(self, hours=6) -> Dict[str, Any]:
        """Get queue depth data over time."""
        queue_data = {
            'timestamps': [],
            'environments': {}
        }
        
        for env in self.environments:
            queue_data['environments'][env] = []
            
            env_config = self.env_configs[env]
            metrics_dir = env_config.get_log_path("metrics")
            queue_file = os.path.join(metrics_dir, "queue_depth.csv")
            
            if os.path.exists(queue_file):
                try:
                    df = pd.read_csv(queue_file)
                    if not df.empty:
                        # Convert timestamp and filter
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        cutoff_time = pd.Timestamp.now() - pd.Timedelta(hours=hours)
                        recent_df = df[df['timestamp'] >= cutoff_time]
                        
                        if not recent_df.empty:
                            # Sample data points (every 10 minutes)
                            recent_df = recent_df.set_index('timestamp').resample('10T')['depth'].mean().reset_index()
                            
                            queue_data['environments'][env] = recent_df['depth'].fillna(0).tolist()
                            
                            # Use first environment's timestamps
                            if not queue_data['timestamps']:
                                queue_data['timestamps'] = recent_df['timestamp'].dt.strftime('%H:%M').tolist()
                
                except Exception as e:
                    print(f"Error processing queue depth for {env}: {e}")
        
        return queue_data
    
    def get_error_heatmap(self, days=7) -> Dict[str, Any]:
        """Get error heatmap data per environment."""
        heatmap_data = {
            'environments': [],
            'error_types': [],
            'error_counts': [],
            'severity_colors': []
        }
        
        all_error_types = set()
        env_error_data = {}
        
        # Collect all error types and data
        for env in self.environments:
            env_config = self.env_configs[env]
            metrics_dir = env_config.get_log_path("metrics")
            error_file = os.path.join(metrics_dir, "error_metrics.csv")
            
            env_error_data[env] = {}
            
            if os.path.exists(error_file):
                try:
                    df = pd.read_csv(error_file)
                    if not df.empty:
                        # Filter last N days
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        cutoff_time = pd.Timestamp.now() - pd.Timedelta(days=days)
                        recent_df = df[df['timestamp'] >= cutoff_time]
                        
                        if not recent_df.empty:
                            # Group by error type
                            error_summary = recent_df.groupby(['error_type', 'severity']).agg({
                                'error_count': 'sum'
                            }).reset_index()
                            
                            for _, row in error_summary.iterrows():
                                error_type = row['error_type']
                                all_error_types.add(error_type)
                                env_error_data[env][error_type] = {
                                    'count': row['error_count'],
                                    'severity': row['severity']
                                }
                
                except Exception as e:
                    print(f"Error processing error heatmap for {env}: {e}")
        
        # Build heatmap matrix
        all_error_types = sorted(list(all_error_types))
        
        for env in self.environments:
            for error_type in all_error_types:
                heatmap_data['environments'].append(env)
                heatmap_data['error_types'].append(error_type)
                
                if error_type in env_error_data[env]:
                    error_info = env_error_data[env][error_type]
                    heatmap_data['error_counts'].append(error_info['count'])
                    heatmap_data['severity_colors'].append(error_info['severity'])
                else:
                    heatmap_data['error_counts'].append(0)
                    heatmap_data['severity_colors'].append('low')
        
        return heatmap_data
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Get comprehensive system overview."""
        return {
            'environment_health': self.get_environment_health(),
            'scaling_activity': self.get_scaling_activity(),
            'deployment_throughput': self.get_deployment_throughput(),
            'queue_depth': self.get_queue_depth_over_time(),
            'error_heatmap': self.get_error_heatmap()
        }