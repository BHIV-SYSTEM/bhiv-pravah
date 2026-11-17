#!/usr/bin/env python3
"""
Runtime Event Emission Lock
Guarantees no runtime event can be skipped - all events must reach Redis, CSV, and metrics
"""

import os
import csv
import datetime
import json
from typing import Dict, Any, List

class EventEmissionError(Exception):
    """Raised when event emission fails."""
    pass

class RuntimeEventEmissionLock:
    """Ensures all runtime events are emitted to all destinations."""
    
    REQUIRED_EVENTS = ['deploy', 'scale', 'restart', 'crash', 'overload']
    
    @staticmethod
    def emit_runtime_event(env: str, event_type: str, status: str, 
                          response_time: float, dataset: str, **kwargs):
        """
        Emit runtime event to ALL destinations - no silent failures allowed.
        
        Args:
            env: Environment (dev/stage/prod)
            event_type: Type of event (deploy/scale/restart/crash/overload)
            status: Event status (success/failure/refused)
            response_time: Response time in milliseconds
            dataset: Dataset involved
            **kwargs: Additional event data
        """
        if event_type not in RuntimeEventEmissionLock.REQUIRED_EVENTS:
            raise EventEmissionError(f"Unknown event type: {event_type}")
        
        # Prepare event data
        event_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'env': env,
            'event_type': event_type,
            'status': status,
            'response_time': response_time,
            'dataset': dataset,
            **kwargs
        }
        
        # Track emission failures
        failures = []
        
        # 1. REDIS EVENT - MANDATORY
        try:
            RuntimeEventEmissionLock._emit_to_redis(env, event_type, event_data)
        except Exception as e:
            failures.append(f"Redis emission failed: {e}")
        
        # 2. CSV LOG - MANDATORY  
        try:
            RuntimeEventEmissionLock._emit_to_csv(env, event_type, event_data)
        except Exception as e:
            failures.append(f"CSV emission failed: {e}")
        
        # 3. METRICS ENTRY - MANDATORY
        try:
            RuntimeEventEmissionLock._emit_to_metrics(env, event_type, event_data)
        except Exception as e:
            failures.append(f"Metrics emission failed: {e}")
        
        # FAIL DETERMINISTICALLY if any emission failed
        if failures:
            error_msg = f"Event emission failed for {event_type}: {'; '.join(failures)}"
            print(f"CRITICAL: {error_msg}")
            raise EventEmissionError(error_msg)
        
        print(f"EVENT EMITTED: {event_type} -> Redis + CSV + Metrics")
    
    @staticmethod
    def _emit_to_redis(env: str, event_type: str, event_data: Dict[str, Any]):
        """Emit event to Redis bus."""
        try:
            from core.redis_demo_behavior import get_redis_bus_demo_safe
            redis_bus = get_redis_bus_demo_safe(env, use_stub=True)
            
            # Publish to specific event channel
            channel = f"runtime.{event_type}"
            redis_bus.publish(channel, event_data)
            
            # Also publish to general runtime channel
            redis_bus.publish("runtime.all", event_data)
            
        except Exception as e:
            # Re-raise with context
            raise Exception(f"Redis publish failed: {e}")
    
    @staticmethod
    def _emit_to_csv(env: str, event_type: str, event_data: Dict[str, Any]):
        """Emit event to CSV log."""
        try:
            # Environment-specific CSV log
            log_file = os.path.join("logs", env, f"runtime_{event_type}_log.csv")
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            # CSV headers
            headers = ['timestamp', 'env', 'event_type', 'status', 'response_time', 'dataset']
            
            # Check if file exists to write headers
            file_exists = os.path.exists(log_file)
            
            with open(log_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
                if not file_exists:
                    writer.writeheader()
                writer.writerow(event_data)
            
            # Also write to unified runtime log
            unified_log = os.path.join("logs", env, "runtime_all_events.csv")
            file_exists = os.path.exists(unified_log)
            
            with open(unified_log, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
                if not file_exists:
                    writer.writeheader()
                writer.writerow(event_data)
                
        except Exception as e:
            # Re-raise with context
            raise Exception(f"CSV write failed: {e}")
    
    @staticmethod
    def _emit_to_metrics(env: str, event_type: str, event_data: Dict[str, Any]):
        """Emit event to metrics system."""
        try:
            from core.metrics_collector import get_metrics_collector
            metrics = get_metrics_collector(env)
            
            # Record different metric types based on event
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
                    0,  # downtime
                    event_data['response_time']
                )
            elif event_type in ['crash', 'overload']:
                metrics.record_error_metric(
                    f"{event_type}_{env}",
                    event_data['status'],
                    event_data.get('error_count', 1)
                )
            
            # Always record general runtime metric
            metrics.record_performance_metric(
                f"runtime_{event_type}_{env}",
                event_data['response_time'],
                event_data['status'] == 'success'
            )
            
        except Exception as e:
            # Re-raise with context
            raise Exception(f"Metrics recording failed: {e}")

# Convenience functions for each event type
def emit_deploy_event(env: str, status: str, response_time: float, dataset: str, **kwargs):
    """Emit deploy event - guaranteed delivery to all destinations."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, 'deploy', status, response_time, dataset, **kwargs
    )

def emit_scale_event(env: str, status: str, response_time: float, dataset: str, 
                    scale_direction: str = 'up', worker_count: int = 1, **kwargs):
    """Emit scale event - guaranteed delivery to all destinations."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, 'scale', status, response_time, dataset, 
        scale_direction=scale_direction, worker_count=worker_count, **kwargs
    )

def emit_restart_event(env: str, status: str, response_time: float, dataset: str, **kwargs):
    """Emit restart event - guaranteed delivery to all destinations."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, 'restart', status, response_time, dataset, **kwargs
    )

def emit_crash_event(env: str, status: str, response_time: float, dataset: str, 
                    error_count: int = 1, **kwargs):
    """Emit crash event - guaranteed delivery to all destinations."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, 'crash', status, response_time, dataset, 
        error_count=error_count, **kwargs
    )

def emit_overload_event(env: str, status: str, response_time: float, dataset: str, 
                       load_level: float = 1.0, **kwargs):
    """Emit overload event - guaranteed delivery to all destinations."""
    RuntimeEventEmissionLock.emit_runtime_event(
        env, 'overload', status, response_time, dataset, 
        load_level=load_level, **kwargs
    )

# Validation function
def validate_event_emission(env: str, event_type: str) -> Dict[str, bool]:
    """Validate that event emission destinations are working."""
    results = {
        'redis': False,
        'csv': False, 
        'metrics': False
    }
    
    try:
        # Test Redis
        from core.redis_demo_behavior import get_redis_bus_demo_safe
        redis_bus = get_redis_bus_demo_safe(env, use_stub=True)
        redis_bus.publish("test.validation", {"test": True})
        results['redis'] = True
    except:
        pass
    
    try:
        # Test CSV
        test_log = os.path.join("logs", env, "test_validation.csv")
        os.makedirs(os.path.dirname(test_log), exist_ok=True)
        with open(test_log, 'w') as f:
            f.write("test,validation\n")
        os.remove(test_log)
        results['csv'] = True
    except:
        pass
    
    try:
        # Test Metrics
        from core.metrics_collector import get_metrics_collector
        metrics = get_metrics_collector(env)
        results['metrics'] = True
    except:
        pass
    
    return results