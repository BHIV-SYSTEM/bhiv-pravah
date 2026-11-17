"""Standardized logging utilities."""

import pandas as pd
import os
from datetime import datetime
from pathlib import Path

def get_log_path(category, metric_type, environment):
    """Get standardized log file path."""
    filename = f"{category}_{metric_type}_{environment}.csv"
    return os.path.join("logs", environment, filename)

def log_event(category, metric_type, environment, data):
    """Log event with standardized format."""
    filepath = get_log_path(category, metric_type, environment)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Add timestamp if not present
    if 'timestamp' not in data:
        data['timestamp'] = datetime.now().isoformat()
    
    # Add environment if not present
    if 'environment' not in data:
        data['environment'] = environment
    
    # Convert to DataFrame and append
    df = pd.DataFrame([data])
    
    if os.path.exists(filepath):
        df.to_csv(filepath, mode='a', header=False, index=False)
    else:
        df.to_csv(filepath, index=False)

def log_deployment(environment, agent_id, dataset_path, status, response_time_ms, action_type="deploy"):
    """Log deployment event."""
    log_event("deploy", "log", environment, {
        'agent_id': agent_id,
        'dataset_path': dataset_path,
        'status': status,
        'response_time_ms': response_time_ms,
        'action_type': action_type
    })

def log_healing(environment, agent_id, issue_type, strategy, status, recovery_time_ms):
    """Log healing event."""
    log_event("heal", "log", environment, {
        'agent_id': agent_id,
        'issue_type': issue_type,
        'strategy': strategy,
        'status': status,
        'recovery_time_ms': recovery_time_ms
    })

def log_metrics(environment, category, metric_type, metrics_data):
    """Log metrics with standardized format."""
    log_event(category, metric_type, environment, metrics_data)