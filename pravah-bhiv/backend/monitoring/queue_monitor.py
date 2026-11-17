#!/usr/bin/env python3
"""
Queue Monitor
Debug and monitor Redis event bus activity
"""

import time
import json
import datetime
import csv
import os
from control_plane.core.redis_event_bus import get_redis_bus
from control_plane.core.env_config import EnvironmentConfig

class QueueMonitor:
    """Monitor and debug Redis event bus."""
    
    def __init__(self, env='dev'):
        self.env_config = EnvironmentConfig(env)
        self.redis_bus = get_redis_bus(env)
        self.log_file = self.env_config.get_log_path("queue_monitor.csv")
        self.message_count = 0
        self._initialize_log()
        
        # Subscribe to all events for monitoring
        self.redis_bus.subscribe("*", self._log_message)
    
    def _initialize_log(self):
        """Initialize queue monitor log."""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'event_type', 'data_summary', 'message_size',
                    'environment', 'message_id'
                ])
    
    def _log_message(self, event_type: str, data: dict):
        """Log intercepted message."""
        self.message_count += 1
        timestamp = datetime.datetime.now().isoformat()
        
        # Create data summary
        data_summary = str(data)[:100] + "..." if len(str(data)) > 100 else str(data)
        message_size = len(json.dumps(data))
        
        # Log to CSV
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, event_type, data_summary, message_size,
                self.env_config.get('environment'), self.message_count
            ])
        
        print(f"📊 [{self.message_count}] {event_type}: {data_summary}")
    
    def print_stats(self):
        """Print current queue statistics."""
        stats = self.redis_bus.get_queue_stats()
        
        print(f"\n📈 Queue Statistics ({self.env_config.get('environment').upper()}):")
        print(f"   Redis Connected: {'✅' if stats['connected'] else '❌'}")
        print(f"   Active Subscribers: {stats['subscribers']}")
        print(f"   Messages Monitored: {self.message_count}")
        print(f"   Message History: {stats['message_history_count']}")
        
        if stats['connected'] and 'redis_version' in stats:
            print(f"   Redis Version: {stats['redis_version']}")
            print(f"   Connected Clients: {stats['connected_clients']}")
            print(f"   Memory Usage: {stats['used_memory_human']}")
            print(f"   Commands Processed: {stats['total_commands_processed']}")
    
    def print_recent_messages(self, limit=10):
        """Print recent messages from history."""
        history = self.redis_bus.get_message_history(limit)
        
        print(f"\n📜 Recent Messages (last {len(history)}):")
        for i, msg in enumerate(history[-limit:], 1):
            timestamp = msg['timestamp'][:19]  # Remove microseconds
            event_type = msg['event_type']
            data_keys = list(msg['data'].keys()) if isinstance(msg['data'], dict) else []
            print(f"   {i}. [{timestamp}] {event_type} -> {data_keys}")
    
    def test_message_flow(self):
        """Test message publishing and receiving."""
        print("\n🧪 Testing message flow...")
        
        # Publish test messages
        test_events = [
            ('test.deploy', {'status': 'success', 'time': 1500}),
            ('test.issue', {'type': 'anomaly', 'severity': 'high'}),
            ('test.heal', {'action': 'restart', 'result': 'success'})
        ]
        
        for event_type, data in test_events:
            self.redis_bus.publish(event_type, data)
            time.sleep(0.1)  # Small delay
        
        print("✅ Test messages published")
        time.sleep(1)  # Wait for processing
        
        self.print_recent_messages(5)
    
    def run_continuous_monitoring(self, interval=30, cycles=1):
        """Run bounded monitoring with periodic stats."""
        if cycles < 0:
            raise ValueError("cycles must be >= 0")

        print(f"🚀 Starting bounded queue monitoring (interval: {interval}s, cycles: {cycles})")
        print(f"📝 Logging to: {self.log_file}")
        
        try:
            if cycles == 0:
                while True:
                    self.print_stats()
                    print(f"⏰ Next update in {interval} seconds...")
                    time.sleep(interval)
            else:
                for idx in range(cycles):
                    self.print_stats()
                    if idx < cycles - 1:
                        print(f"⏰ Next update in {interval} seconds...")
                        time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        finally:
            self.redis_bus.stop()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Queue Monitor")
    parser.add_argument("--env", choices=['dev', 'stage', 'prod'], default='dev')
    parser.add_argument("--continuous", action='store_true',
                       help='Run continuous monitoring')
    parser.add_argument("--interval", type=int, default=30,
                       help='Monitoring interval in seconds')
    parser.add_argument("--cycles", type=int, default=1,
                       help='Number of monitoring cycles (must be >=1)')
    parser.add_argument("--test", action='store_true',
                       help='Run message flow test')
    parser.add_argument("--stats", action='store_true',
                       help='Show current statistics')
    parser.add_argument("--history", type=int, default=10,
                       help='Show recent message history')
    
    args = parser.parse_args()
    
    monitor = QueueMonitor(args.env)
    
    if args.test:
        monitor.test_message_flow()
    elif args.stats:
        monitor.print_stats()
        monitor.print_recent_messages(args.history)
    elif args.continuous:
        monitor.run_continuous_monitoring(args.interval, args.cycles)
    else:
        # Default: show stats and recent messages
        monitor.print_stats()
        monitor.print_recent_messages(args.history)