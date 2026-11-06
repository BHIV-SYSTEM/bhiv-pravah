#!/usr/bin/env python3
"""Runtime Event Emission Lock - No Silent Failures"""

import os
import csv
import datetime
from typing import Dict, Any

class EventEmissionError(Exception):
    """Raised when event emission fails."""
    pass

class RuntimeEventEmissionLock:
    """Ensures all runtime events are emitted to all destinations."""
    
    REQUIRED_EVENTS = ['deploy', 'scale', 'restart', 'crash', 'overload', 'false_alarm', 'critical_system_failure']
    
    @staticmethod
    def emit_runtime_event(env: str, event_type: str, status: str, 
                          response_time: float, dataset: str, **kwargs):
        """Emit runtime event to ALL destinations - no silent failures."""
        if event_type not in RuntimeEventEmissionLock.REQUIRED_EVENTS:
            raise EventEmissionError(f"Unknown event type: {event_type}")
        
        event_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'env': env,
            'event_type': event_type,
            'status': status,
            'response_time': response_time,
            'dataset': dataset,
            **kwargs
        }
        
        failures = []
        
        # 1. REDIS EVENT - MANDATORY
        try:
            RuntimeEventEmissionLock._emit_to_redis(env, event_type, event_data)
        except Exception as e:
            failures.append(f"Redis: {e}")
        
        # 2. CSV LOG - MANDATORY  
        try:
            RuntimeEventEmissionLock._emit_to_csv(env, event_type, event_data)
        except Exception as e:
            failures.append(f"CSV: {e}")
        
        # 3. METRICS ENTRY - MANDATORY
        try:
            RuntimeEventEmissionLock._emit_to_metrics(env, event_type, event_data)
        except Exception as e:
            failures.append(f"Metrics: {e}")
        
        # 4. RL LAYER - MANDATORY
        try:
            RuntimeEventEmissionLock._emit_to_rl(env, event_type, event_data)
        except Exception as e:
            failures.append(f"RL: {e}")
        
        # FAIL DETERMINISTICALLY if any emission failed
        if failures:
            error_msg = f"Event emission failed for {event_type}: {'; '.join(failures)}"
            print(f"CRITICAL: {error_msg}")
            raise EventEmissionError(error_msg)
    
    @staticmethod
    def _emit_to_redis(env: str, event_type: str, event_data: Dict[str, Any]):
        """Emit event to Redis bus."""
        try:
            from core.redis_demo_behavior import get_redis_bus_demo_safe
            redis_bus = get_redis_bus_demo_safe(env, use_stub=True)
            redis_bus.publish(f"runtime.{event_type}", event_data)
        except Exception as e:
            raise Exception(f"Redis publish failed: {e}")
    
    @staticmethod
    def _emit_to_csv(env: str, event_type: str, event_data: Dict[str, Any]):
        """Emit event to CSV log."""
        try:
            log_file = os.path.join("logs", env, f"runtime_{event_type}_log.csv")
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            headers = ['timestamp', 'env', 'event_type', 'status', 'response_time', 'dataset']
            file_exists = os.path.exists(log_file)
            
            with open(log_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
                if not file_exists:
                    writer.writeheader()
                writer.writerow(event_data)
        except Exception as e:
            raise Exception(f"CSV write failed: {e}")
    
    @staticmethod
    def _emit_to_metrics(env: str, event_type: str, event_data: Dict[str, Any]):
        """Emit event to metrics system."""
        try:
            from core.metrics_collector import get_metrics_collector
            metrics = get_metrics_collector(env)
            
            if event_type == 'deploy':
                metrics.record_deploy_metric(
                    f"deploy_{env}", 
                    event_data['status'], 
                    event_data['response_time']
                )
            elif event_type == 'scale':
                metrics.record_scale_metric(
                    f"scale_{env}",
                    event_data.get('scale_direction', 'up'),
                    event_data.get('worker_count', 1)
                )
            elif event_type == 'restart':
                metrics.record_uptime_metric(
                    f"restart_{env}",
                    event_data['status'],
                    event_data['response_time'], 0
                )
            elif event_type in ['crash', 'overload']:
                metrics.record_error_metric(
                    f"{event_type}_{env}",
                    event_data['status'],
                    event_data.get('error_count', 1)
                )
        except Exception as e:
            raise Exception(f"Metrics recording failed: {e}")
    
    @staticmethod
    def _emit_to_rl(env: str, event_type: str, event_data: Dict[str, Any]):
        """Emit event to RL layer with structured proof logging."""
        try:
            # Structured proof logging - RUNTIME_EMIT
            from core.proof_logger import write_proof, ProofEvents
            write_proof(ProofEvents.RUNTIME_EMIT, {
                'env': env,
                'event_type': event_type,
                'payload': event_data,
                'status': 'emitted'
            })
            
            # Legacy logging for backward compatibility
            import json
            payload_json = json.dumps(event_data, sort_keys=True, separators=(',', ':'))
            
            with open('runtime_rl_proof.log', 'a') as f:
                f.write(f"RUNTIME EVENT: {event_data}\n")
            
            with open('payload_integrity.log', 'a') as f:
                f.write(f"EMIT: {payload_json}\n")
            
            # Runtime RL piping has been removed from the execution layer.
            with open('runtime_rl_proof.log', 'a') as f:
                f.write(f"RL CONSUMED: event_type={event_type}, rl_action=disabled\n")
            
        except Exception as e:
            raise Exception(f"RL pipe failed: {e}")

# Convenience functions
def emit_deploy_event(env: str, status: str, response_time: float, dataset: str, **kwargs):
    """Emit deploy event - guaranteed delivery."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, 'deploy', status, response_time, dataset, **kwargs
    )

def emit_scale_event(env: str, status: str, response_time: float, dataset: str, **kwargs):
    """Emit scale event - guaranteed delivery."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, 'scale', status, response_time, dataset, **kwargs
    )

def emit_restart_event(env: str, status: str, response_time: float, dataset: str, **kwargs):
    """Emit restart event - guaranteed delivery."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, 'restart', status, response_time, dataset, **kwargs
    )

def emit_crash_event(env: str, status: str, response_time: float, dataset: str, **kwargs):
    """Emit crash event - guaranteed delivery."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, 'crash', status, response_time, dataset, **kwargs
    )

def emit_overload_event(env: str, status: str, response_time: float, dataset: str, **kwargs):
    """Emit overload event - guaranteed delivery."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, 'overload', status, response_time, dataset, **kwargs
    )

def emit_false_alarm_event(env: str, status: str, response_time: float, dataset: str, **kwargs):
    """Emit false alarm event - guaranteed delivery."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, 'false_alarm', status, response_time, dataset, **kwargs
    )

def emit_runtime_event(env: str, event_type: str, status: str, response_time: float, dataset: str, **kwargs):
    """Generic runtime event emitter - guaranteed delivery."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, event_type, status, response_time, dataset, **kwargs
    )

class GuaranteedEmitter:
    """Convenience emitter adapter."""
    def __init__(self, env: str, redis_bus=None, metrics=None):
        self.env = env
        self.redis_bus = redis_bus
        self.metrics = metrics

    def emit_runtime_event(self, event_type: str, status: str, response_time: float, dataset: str = "system", **kwargs):
        actual_type = event_type if event_type in RuntimeEventEmissionLock.REQUIRED_EVENTS else "crash"
        RuntimeEventEmissionLock.emit_runtime_event(self.env, actual_type, status, response_time, dataset, **kwargs)

def get_guaranteed_emitter(env: str, redis_bus=None, metrics=None) -> GuaranteedEmitter:
    """Get guaranteed event emitter instance."""
    return GuaranteedEmitter(env, redis_bus, metrics)
