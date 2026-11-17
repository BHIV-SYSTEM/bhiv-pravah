#!/usr/bin/env python3
"""
Multi-Deploy Agent
Manages multiple deploy agent workers for horizontal scaling
"""

import os
import time
import threading
import queue
import csv
import datetime
from control_plane.agents.deploy_agent import DeployAgent
from control_plane.core.env_config import EnvironmentConfig
from control_plane.core.redis_event_bus import get_redis_bus
from control_plane.core.metrics_collector import get_metrics_collector
from control_plane.core.prod_safety import validate_prod_action, ProductionSafetyError
from control_plane.core.stage_determinism import StageDeterminismLock, log_determinism_status

class MultiDeployAgent:
    """Manages multiple deploy agent workers for horizontal scaling."""
    
    def __init__(self, env='dev', workers=3):
        self.env = env
        self.workers = workers
        self.env_config = EnvironmentConfig(env)
        # Demo-safe Redis behavior - no silent mock mode
        from control_plane.core.redis_demo_behavior import get_redis_bus_demo_safe, RedisUnavailableError
        
        try:
            # Try Redis with explicit stub fallback for demo
            self.redis_bus = get_redis_bus_demo_safe(env, use_stub=True)
        except RedisUnavailableError as e:
            print(f"CRITICAL: {e}")
            raise  # Fail deterministically
        self.metrics = get_metrics_collector(env)
        
        # Initialize workers
        self.deploy_agents = []
        for i in range(1, workers + 1):
            agent = DeployAgent('deployment_log.csv', env, worker_id=i)
            self.deploy_agents.append(agent)
        
        # Work queue for load balancing
        self.work_queue = queue.Queue()
        self.worker_threads = []
        self.running = False
        
        # Performance tracking
        self.throughput_log = os.path.join("logs", env, "performance", "throughput_log.csv")
        self._initialize_throughput_log()
        
        print(f"Initialized Multi-Deploy Agent with {workers} workers for {env.upper()}")
    
    def _initialize_throughput_log(self):
        """Initialize throughput performance log."""
        os.makedirs(os.path.dirname(self.throughput_log), exist_ok=True)
        if not os.path.exists(self.throughput_log):
            with open(self.throughput_log, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'total_workers', 'active_workers', 'queue_size',
                    'requests_per_second', 'avg_response_time', 'environment'
                ])
    
    def start_workers(self):
        """Start all worker threads."""
        if self.running:
            return
        
        self.running = True
        
        for i, agent in enumerate(self.deploy_agents):
            thread = threading.Thread(
                target=self._worker_loop,
                args=(agent, i + 1),
                daemon=True
            )
            thread.start()
            self.worker_threads.append(thread)
        
        print(f"Started {len(self.worker_threads)} worker threads")
        
        # Start performance monitoring
        monitor_thread = threading.Thread(target=self._monitor_performance, daemon=True)
        monitor_thread.start()
    
    def stop_workers(self):
        """Stop all worker threads."""
        self.running = False
        
        # Add poison pills to wake up workers
        for _ in self.deploy_agents:
            self.work_queue.put(None)
        
        # Wait for threads to finish
        for thread in self.worker_threads:
            thread.join(timeout=1)
        
        print("All workers stopped")
    
    def _worker_loop(self, agent, worker_id):
        """Process queued work until the agent is stopped."""
        from control_plane.core.guaranteed_events import emit_deploy_event, emit_scale_event

        while self.running:
            try:
                work_item = self.work_queue.get(timeout=1)
                if work_item is None:
                    self.work_queue.task_done()
                    return

                dataset, action_type = work_item

                if action_type == 'deploy':
                    from utils import trigger_dashboard_deployment
                    status, response_time = trigger_dashboard_deployment(env=self.env)
                else:
                    if StageDeterminismLock.is_stage_env(self.env):
                        response_time = StageDeterminismLock.get_deterministic_response_time(action_type, worker_id)
                        time.sleep(response_time / 1000)
                        status = 'success'
                        log_determinism_status(self.env, f"Worker {worker_id} {action_type} timing")
                    else:
                        time.sleep(0.5 + (worker_id * 0.1))
                        status, response_time = 'success', 500 + (worker_id * 100)

                try:
                    if action_type == 'deploy':
                        emit_deploy_event(self.env, status, response_time, dataset)
                    elif action_type in ['scale_up', 'scale_down', 'scale']:
                        emit_scale_event(self.env, status, response_time, dataset)
                    else:
                        emit_deploy_event(self.env, status, response_time, dataset)
                except Exception as e:
                    print(f"CRITICAL: Event emission failed for {action_type}: {e}")

                agent.log_deployment(dataset, status, response_time, action_type)
                self.work_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Worker {worker_id} error: {e}")
                try:
                    self.work_queue.task_done()
                except ValueError:
                    pass

    def submit_deployment(self, dataset, action_type='deploy'):
        """Submit deployment work to the queue."""
        # Production safety check
        try:
            validate_prod_action(action_type, self.env)
        except ProductionSafetyError as e:
            # Do NOT execute - emit refusal event, log refusal, return deterministic response
            refusal_event = {
                "event": "action_refused",
                "env": self.env,
                "status": "refused",
                "latency": 0,
                "timestamp": datetime.datetime.now().isoformat(),
                "action_type": action_type,
                "dataset": dataset,
                "reason": "prod_safety_block",
                "error_message": str(e)
            }
            
            # Emit refusal event to Redis
            self.redis_bus.publish("action.refused", refusal_event)
            
            # Log refusal to CSV
            with open(self.throughput_log, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.datetime.now().isoformat(), self.workers, 0, 0,
                    0, 0, f"{self.env}_REFUSED_{action_type}"
                ])
            
            print(f"Action refused: {action_type} blocked in {self.env} environment")
            
            # Return deterministic response
            return False
        
        self.work_queue.put((dataset, action_type))
        
        # Publish work submission event
        self.redis_bus.publish('work.submitted', {
            'dataset': dataset,
            'action_type': action_type,
            'queue_size': self.work_queue.qsize(),
            'workers': self.workers,
            'environment': self.env
        })
        return True
    
    def _monitor_performance(self):
        """Run a single non-loop performance snapshot."""
        last_check = time.time()
        last_request_count = 0

        if not self.running:
            return

        current_time = time.time()

        # Calculate metrics
        queue_size = self.work_queue.qsize()
        active_workers = sum(1 for t in self.worker_threads if t.is_alive())

        # Estimate requests per second (simplified)
        time_diff = current_time - last_check
        requests_per_second = 0

        # Log performance metrics
        timestamp = datetime.datetime.now().isoformat()
        with open(self.throughput_log, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, self.workers, active_workers, queue_size,
                requests_per_second, 0, self.env
            ])

        # Record queue metrics
        self.metrics.record_queue_metric(
            f"deploy_queue_{self.env}", queue_size,
            enqueue_rate=0, dequeue_rate=0
        )

        # Record uptime metrics for multi-deploy service
        uptime_seconds = current_time - (last_check if hasattr(self, '_start_time') else current_time)
        if not hasattr(self, '_start_time'):
            self._start_time = current_time

        self.metrics.record_uptime_metric(
            f"multi_deploy_agent_{self.env}", "running",
            uptime_seconds, 0
        )
    
    def get_status(self):
        """Get current status of the multi-deploy agent."""
        return {
            'workers': self.workers,
            'active_workers': sum(1 for t in self.worker_threads if t.is_alive()),
            'queue_size': self.work_queue.qsize(),
            'running': self.running,
            'environment': self.env
        }

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Deploy Agent")
    parser.add_argument("--env", choices=['dev', 'stage', 'prod'], default='dev')
    parser.add_argument("--workers", type=int, default=3, help='Number of worker agents')
    parser.add_argument("--test", action='store_true', help='Run test workload')
    parser.add_argument("--status-cycles", type=int, default=0, help='Number of status snapshots; 0 means run continuously')
    
    args = parser.parse_args()
    
    # Create multi-deploy agent
    multi_agent = MultiDeployAgent(args.env, args.workers)
    multi_agent.start_workers()
    
    if args.test:
        print("Running test workload...")
        
        # Submit test work
        for i in range(10):
            multi_agent.submit_deployment(f'test_dataset_{i}.csv', 'deploy')
            time.sleep(0.2)
        
        # Wait for work to complete
        multi_agent.work_queue.join()
        print("Test workload completed")
    
    try:
        print("Multi-Deploy Agent running in bounded status mode.")
        if args.status_cycles < 0:
            raise ValueError("--status-cycles must be >= 0")
        if args.status_cycles == 0:
            while True:
                status = multi_agent.get_status()
                print(f"Status: {status['active_workers']}/{status['workers']} workers, "
                      f"queue: {status['queue_size']}")
                time.sleep(10)
        else:
            for _ in range(args.status_cycles):
                status = multi_agent.get_status()
                print(f"Status: {status['active_workers']}/{status['workers']} workers, "
                      f"queue: {status['queue_size']}")
                time.sleep(10)
    except KeyboardInterrupt:
        print("\nStopping Multi-Deploy Agent...")
        multi_agent.stop_workers()
