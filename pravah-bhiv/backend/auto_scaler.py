#!/usr/bin/env python3
"""Automated Scaling Policy Engine"""
import time
import threading
from control_plane.agents.multi_deploy_agent import MultiDeployAgent
from control_plane.core.env_config import EnvironmentConfig
from control_plane.core.metrics_collector import get_metrics_collector

class AutoScaler:
    """Automated scaling based on queue depth and load metrics."""
    
    def __init__(self, env='dev'):
        self.env = env
        self.env_config = EnvironmentConfig(env)
        self.metrics = get_metrics_collector(env)
        self.multi_agent = None
        self.running = False
        
        self.scaling_policy = {
            'min_workers': 1,
            'max_workers': 5,
            'scale_up_threshold': 10,    # queue depth
            'scale_down_threshold': 2,   # queue depth
            'scale_up_cooldown': 60,     # seconds
            'scale_down_cooldown': 120,  # seconds
            'check_interval': 30         # seconds
        }
        
        self.last_scale_action = 0
        self.current_workers = 1
    
    def start_auto_scaling(self):
        """Start automated scaling loop."""
        if self.running:
            return
        
        self.running = True
        self.multi_agent = MultiDeployAgent(self.env, workers=self.current_workers)
        self.multi_agent.start_workers()
        
        scaling_thread = threading.Thread(target=self._scaling_loop, daemon=True)
        scaling_thread.start()
        print(f"🔄 Auto-scaler started for {self.env.upper()}")
    
    def stop_auto_scaling(self):
        """Stop automated scaling."""
        self.running = False
        if self.multi_agent:
            self.multi_agent.stop_workers()
        print("🛑 Auto-scaler stopped")
    
    def _scaling_loop(self):
        """Main scaling decision loop."""
        while self.running:
            try:
                current_time = time.time()
                queue_depth = self._get_queue_depth()
                
                scale_decision = self._make_scale_decision(queue_depth, current_time)
                
                if scale_decision == 'scale_up':
                    self._scale_up()
                    self.last_scale_action = current_time
                elif scale_decision == 'scale_down':
                    self._scale_down()
                    self.last_scale_action = current_time
                
                self._log_scaling_metrics(queue_depth, scale_decision)
                time.sleep(self.scaling_policy['check_interval'])
                
            except Exception as e:
                print(f"❌ Scaling loop error: {e}")
                time.sleep(self.scaling_policy['check_interval'])
    
    def _get_queue_depth(self):
        """Get current queue depth."""
        if self.multi_agent and hasattr(self.multi_agent, 'work_queue'):
            return self.multi_agent.work_queue.qsize()
        return 0
    
    def get_recommendation(self, queue_depth: int) -> dict:
        """
        Get scaling recommendation without executing.
        Used by the Arbitrator.
        """
        current_time = time.time()
        action = self._make_scale_decision(queue_depth, current_time)
        
        reason = "queue_depth_within_limits"
        if action == 'scale_up':
            reason = f"queue_depth {queue_depth} > threshold {self.scaling_policy['scale_up_threshold']}"
        elif action == 'scale_down':
            reason = f"queue_depth {queue_depth} < threshold {self.scaling_policy['scale_down_threshold']}"
            
        return {
            "action": action if action != 'no_action' else 'noop',
            "reason": reason,
            "confidence": 1.0,  # Rules are always confident
            "source": "auto_scaler_rules"
        }

    def _make_scale_decision(self, queue_depth, current_time):
        """Make scaling decision based on policy."""
        cooldown_elapsed = current_time - self.last_scale_action
        
        # Scale up conditions
        if (queue_depth >= self.scaling_policy['scale_up_threshold'] and
            self.current_workers < self.scaling_policy['max_workers'] and
            cooldown_elapsed >= self.scaling_policy['scale_up_cooldown']):
            return 'scale_up'
        
        # Scale down conditions
        if (queue_depth <= self.scaling_policy['scale_down_threshold'] and
            self.current_workers > self.scaling_policy['min_workers'] and
            cooldown_elapsed >= self.scaling_policy['scale_down_cooldown']):
            return 'scale_down'
        
        return 'no_action'
    
    def _scale_up(self):
        """Scale up workers."""
        new_worker_count = min(self.current_workers + 1, self.scaling_policy['max_workers'])
        if new_worker_count > self.current_workers:
            self.multi_agent.add_worker()
            self.current_workers = new_worker_count
            print(f"📈 Scaled UP to {self.current_workers} workers")
    
    def _scale_down(self):
        """Scale down workers."""
        new_worker_count = max(self.current_workers - 1, self.scaling_policy['min_workers'])
        if new_worker_count < self.current_workers:
            self.multi_agent.remove_worker()
            self.current_workers = new_worker_count
            print(f"📉 Scaled DOWN to {self.current_workers} workers")
    
    def _log_scaling_metrics(self, queue_depth, decision):
        """Log scaling metrics."""
        self.metrics.record_queue_metric(f"auto_scaler_{self.env}", queue_depth, 
                                       self.current_workers, float(time.time()))
        
        if decision != 'no_action':
            print(f"🎯 [{self.env.upper()}] Queue: {queue_depth}, Workers: {self.current_workers}, Action: {decision}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=['dev', 'stage', 'prod'], default='dev')
    args = parser.parse_args()
    
    scaler = AutoScaler(args.env)
    scaler.start_auto_scaling()
    
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        scaler.stop_auto_scaling()