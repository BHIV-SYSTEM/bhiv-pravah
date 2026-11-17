#!/usr/bin/env python3
"""
Infrastructure Health Monitor
Logs daily system status to infra_health_log.csv
"""

import os
import csv
import datetime
import psutil
import subprocess
import json
from control_plane.core.env_config import EnvironmentConfig
from control_plane.core.contracts import validate_monitor_output


class InfraHealthMonitor:
    """Monitors and logs infrastructure health metrics."""
    
    def __init__(self, env='dev'):
        self.env_config = EnvironmentConfig(env)
        self.log_file = self.env_config.get_log_path("infra_health_log.csv")
        self._initialize_log()
    
    def _initialize_log(self):
        """Initialize log file with headers."""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'cpu_percent', 'memory_percent', 'disk_percent',
                    'docker_status', 'containers_running', 'containers_total',
                    'redis_status', 'system_health', 'environment'
                ])
    
    def get_system_metrics(self):
        """Collect system performance metrics."""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent
        }
    
    def check_docker_status(self):
        """Check Docker daemon and container status."""
        try:
            result = subprocess.run(['docker', 'ps', '--format', 'json'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        containers.append(json.loads(line))
                
                running = len([c for c in containers if 'Up' in c.get('Status', '')])
                total = len(containers)
                
                return 'healthy', running, total
            else:
                return 'unhealthy', 0, 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return 'unavailable', 0, 0
    
    def check_redis_status(self):
        """Check Redis connectivity."""
        try:
            import redis
            r = redis.Redis(
                host=self.env_config.get('redis_host', 'localhost'),
                port=self.env_config.get('redis_port', 6379),
                socket_timeout=5
            )
            r.ping()
            return 'healthy'
        except Exception:
            return 'unhealthy'
    
    # def calculate_system_health(self, metrics, docker_status, redis_status):
    #     """Calculate overall system health score."""
    #     score = 100
        
    #     # CPU penalty
    #     if metrics['cpu_percent'] > 80:
    #         score -= 20
    #     elif metrics['cpu_percent'] > 60:
    #         score -= 10
        
    #     # Memory penalty
    #     if metrics['memory_percent'] > 85:
    #         score -= 20
    #     elif metrics['memory_percent'] > 70:
    #         score -= 10
        
    #     # Disk penalty
    #     if metrics['disk_percent'] > 90:
    #         score -= 15
    #     elif metrics['disk_percent'] > 80:
    #         score -= 5
        
    #     # Docker penalty
    #     if docker_status == 'unhealthy':
    #         score -= 25
    #     elif docker_status == 'unavailable':
    #         score -= 40
        
    #     # Redis penalty
    #     if redis_status == 'unhealthy':
    #         score -= 15
        
    #     return max(0, score)
    
    # def log_health_status(self):
    #     """Collect and log current health status."""
    #     timestamp = datetime.datetime.now().isoformat()
        
    #     # Collect metrics
    #     metrics = self.get_system_metrics()
    #     docker_status, containers_running, containers_total = self.check_docker_status()
    #     redis_status = self.check_redis_status()
        
    #     # Calculate health score
    #     health_score = self.calculate_system_health(metrics, docker_status, redis_status)
        
    #     # Log to CSV
    #     with open(self.log_file, 'a', newline='') as f:
    #         writer = csv.writer(f)
    #         writer.writerow([
    #             timestamp,
    #             round(metrics['cpu_percent'], 2),
    #             round(metrics['memory_percent'], 2),
    #             round(metrics['disk_percent'], 2),
    #             docker_status,
    #             containers_running,
    #             containers_total,
    #             redis_status,
    #             health_score,
    #             self.env_config.get('environment')
    #         ])
        
    #     print(f"[{self.env_config.get('environment').upper()}] Health logged: {health_score}% "
    #           f"(CPU: {metrics['cpu_percent']:.1f}%, MEM: {metrics['memory_percent']:.1f}%, "
    #           f"Docker: {docker_status}, Redis: {redis_status})")
        
    #     return health_score

    def log_health_status(self):

        metrics = self.get_system_metrics()
        docker_status, containers_running, containers_total = self.check_docker_status()
        redis_status = self.check_redis_status()

        issue_detected = False
        issue_type = None

        if metrics['cpu_percent'] > 90:
            issue_detected = True
            issue_type = "high_cpu"

        elif metrics['memory_percent'] > 90:
            issue_detected = True
            issue_type = "high_memory"

        elif docker_status != "healthy":
            issue_detected = True
            issue_type = "docker_unavailable"

        elif redis_status != "healthy":
            issue_detected = True
            issue_type = "redis_unhealthy"

        status = "healthy" if not issue_detected else "unhealthy"

        output = {
            "service_id": "infra_system",
            "cpu": metrics['cpu_percent'],
            "memory": metrics['memory_percent'],
            "error_rate": 0.0,
            "status": status,
            "issue_detected": issue_detected,
            "issue_type": issue_type
        }
        validate_monitor_output(output)

        print("📡 Monitoring Output:", output)

        return output

    def run_continuous_monitoring(self, interval_seconds=30):
        """Run health checks continuously so the container stays alive."""
        print(f"🚀 Starting infrastructure health monitoring (interval: {interval_seconds}s)")
        print(f"📝 Logging to: {self.log_file}")

        try:
            while True:
                self.log_health_status()
                print(f"⏰ Next update in {interval_seconds} seconds...")
                import time
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n🛑 Health monitoring stopped by user")













if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Infrastructure Health Monitor")
    parser.add_argument("--env", choices=['dev', 'stage', 'prod'], default='dev')
    parser.add_argument("--continuous", action='store_true', help='Run continuous monitoring')
    parser.add_argument("--interval", type=int, default=30, help='Monitoring interval in seconds')
    args = parser.parse_args()
    
    monitor = InfraHealthMonitor(args.env)
    if args.continuous:
        monitor.run_continuous_monitoring(args.interval)
    else:
        monitor.log_health_status()