#!/usr/bin/env python3
"""Agent Heartbeat System"""
import csv
import os
import time
import datetime
import threading

class HeartbeatMonitor:
    """Monitors agent heartbeats."""
    
    def __init__(self, agent_name: str, env: str = 'dev', interval: int = 30):
        self.agent_name = agent_name
        self.env = env
        self.interval = interval
        self.running = False
        self.thread = None
        self.log_file = f'logs/{env}/system_health_check.csv'
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """Ensure heartbeat log file exists."""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'agent_name', 'status', 'environment', 'heartbeat_interval'])
    
    def log_heartbeat(self):
        """Log a single heartbeat."""
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.datetime.now().isoformat(),
                self.agent_name,
                'alive',
                self.env,
                self.interval
            ])
    
    def start(self):
        """Start heartbeat monitoring."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop heartbeat monitoring."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def _heartbeat_loop(self):
        """Heartbeat loop."""
        while self.running:
            self.log_heartbeat()
            time.sleep(self.interval)

def validate_heartbeats(env: str = 'dev', max_age: int = 60) -> dict:
    """Validate agent heartbeats."""
    log_file = f'logs/{env}/system_health_check.csv'
    
    if not os.path.exists(log_file):
        return {'healthy': False, 'error': 'No heartbeat log found'}
    
    import pandas as pd
    df = pd.read_csv(log_file)
    
    if df.empty:
        return {'healthy': False, 'error': 'No heartbeats recorded'}
    
    # Check latest heartbeats
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    latest = df.groupby('agent_name')['timestamp'].max()
    
    current_time = pd.Timestamp.now()
    stale_agents = []
    
    for agent, last_heartbeat in latest.items():
        age = (current_time - last_heartbeat).total_seconds()
        if age > max_age:
            stale_agents.append({'agent': agent, 'age': age})
    
    return {
        'healthy': len(stale_agents) == 0,
        'total_agents': len(latest),
        'stale_agents': stale_agents,
        'latest_heartbeats': latest.to_dict()
    }