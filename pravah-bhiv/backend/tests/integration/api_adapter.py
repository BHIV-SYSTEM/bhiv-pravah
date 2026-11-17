#!/usr/bin/env python3
"""
API Adapter for Integration with Learning/Automation Layer
Provides standardized access to logs and system status
"""

import os
import pandas as pd
import json
import datetime
from typing import Dict, List, Any, Optional
from core.env_config import EnvironmentConfig
from core.metrics_collector import get_metrics_collector

class APIAdapter:
    """Unified API adapter for automation agents."""
    
    def __init__(self, env='dev'):
        self.env = env
        self.env_config = EnvironmentConfig(env)
        self.metrics = get_metrics_collector(env)
    
    def read_deployment_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Read deployment logs in standardized format."""
        log_file = self.env_config.get_log_path("deployment_log.csv")
        
        if not os.path.exists(log_file):
            return []
        
        try:
            df = pd.read_csv(log_file)
            if df.empty:
                return []
            
            # Convert to standardized event schema
            events = []
            for _, row in df.tail(limit).iterrows():
                event = {
                    "event": "deployment",
                    "env": self.env,
                    "status": row.get("status", "unknown"),
                    "latency": float(row.get("response_time_ms", 0)),
                    "timestamp": row.get("timestamp", ""),
                    "dataset": row.get("dataset_changed", ""),
                    "action_type": row.get("action_type", "deploy"),
                    "worker_id": row.get("worker_id", 1)
                }
                events.append(event)
            
            return events
            
        except Exception as e:
            print(f"Error reading deployment logs: {e}")
            return []
    
    def read_healing_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Read healing logs in standardized format."""
        log_file = self.env_config.get_log_path("healing_log.csv")
        
        if not os.path.exists(log_file):
            return []
        
        try:
            df = pd.read_csv(log_file)
            if df.empty:
                return []
            
            events = []
            for _, row in df.tail(limit).iterrows():
                event = {
                    "event": "healing",
                    "env": self.env,
                    "status": row.get("status", "unknown"),
                    "latency": float(row.get("response_time_ms", 0)),
                    "timestamp": row.get("timestamp", ""),
                    "strategy": row.get("strategy", "unknown")
                }
                events.append(event)
            
            return events
            
        except Exception as e:
            print(f"Error reading healing logs: {e}")
            return []
    
    def read_issue_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Read issue detection logs in standardized format."""
        log_file = self.env_config.get_log_path("issue_log.csv")
        
        if not os.path.exists(log_file):
            return []
        
        try:
            df = pd.read_csv(log_file)
            if df.empty:
                return []
            
            events = []
            for _, row in df.tail(limit).iterrows():
                event = {
                    "event": "issue_detected",
                    "env": self.env,
                    "status": "detected",
                    "latency": 0,
                    "timestamp": row.get("timestamp", ""),
                    "failure_type": row.get("failure_state", "unknown"),
                    "reason": row.get("reason", "")
                }
                events.append(event)
            
            return events
            
        except Exception as e:
            print(f"Error reading issue logs: {e}")
            return []
    
    def read_metrics_logs(self, metric_type: str = "all", limit: int = 100) -> List[Dict[str, Any]]:
        """Read metrics logs in standardized format."""
        metrics_dir = self.env_config.get_log_path("metrics")
        
        if metric_type == "all":
            metric_files = [
                "uptime_metrics.csv",
                "latency_metrics.csv", 
                "queue_depth.csv",
                "deploy_success_rate.csv",
                "error_metrics.csv"
            ]
        else:
            metric_files = [f"{metric_type}.csv"]
        
        all_events = []
        
        for metric_file in metric_files:
            file_path = os.path.join(metrics_dir, metric_file)
            
            if not os.path.exists(file_path):
                continue
            
            try:
                df = pd.read_csv(file_path)
                if df.empty:
                    continue
                
                event_type = metric_file.replace('.csv', '').replace('_', '_')
                
                for _, row in df.tail(limit).iterrows():
                    event = {
                        "event": f"metric_{event_type}",
                        "env": self.env,
                        "status": "recorded",
                        "latency": 0,
                        "timestamp": row.get("timestamp", ""),
                        "metric_data": dict(row)
                    }
                    all_events.append(event)
                    
            except Exception as e:
                print(f"Error reading {metric_file}: {e}")
        
        return sorted(all_events, key=lambda x: x["timestamp"])[-limit:]
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status in standardized format."""
        status = {
            "event": "system_status",
            "env": self.env,
            "status": "healthy",
            "latency": 0,
            "timestamp": datetime.datetime.now().isoformat(),
            "components": {},
            "infra_health": self._get_infra_health(),
            "scaling_decisions": self._get_scaling_decisions(),
            "cluster_load": self._get_cluster_load()
        }
        
        # Check deployment status
        deploy_events = self.read_deployment_logs(limit=1)
        if deploy_events:
            last_deploy = deploy_events[-1]
            status["components"]["deployment"] = {
                "status": last_deploy["status"],
                "last_update": last_deploy["timestamp"]
            }
        
        # Check healing status
        healing_events = self.read_healing_logs(limit=1)
        if healing_events:
            last_heal = healing_events[-1]
            status["components"]["healing"] = {
                "status": last_heal["status"],
                "last_update": last_heal["timestamp"]
            }
        
        # Check for recent issues
        issue_events = self.read_issue_logs(limit=5)
        recent_issues = len([e for e in issue_events 
                           if (datetime.datetime.now() - 
                               pd.to_datetime(e["timestamp"])).total_seconds() < 3600])
        
        status["components"]["issues"] = {
            "recent_count": recent_issues,
            "status": "warning" if recent_issues > 0 else "healthy"
        }
        
        # Overall system status
        component_statuses = [comp.get("status", "unknown") 
                            for comp in status["components"].values()]
        
        if "failure" in component_statuses or recent_issues > 3:
            status["status"] = "critical"
        elif "warning" in component_statuses or recent_issues > 0:
            status["status"] = "warning"
        else:
            status["status"] = "healthy"
        
        return status
    
    def get_unified_event_stream(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get unified event stream for automation agents."""
        all_events = []
        
        # Collect all event types
        all_events.extend(self.read_deployment_logs(limit))
        all_events.extend(self.read_healing_logs(limit))
        all_events.extend(self.read_issue_logs(limit))
        
        # Sort by timestamp
        try:
            all_events.sort(key=lambda x: pd.to_datetime(x["timestamp"]))
        except:
            pass  # Keep original order if timestamp parsing fails
        
        return all_events[-limit:]
    
    def export_events_json(self, output_file: str = None, limit: int = 1000) -> str:
        """Export events to JSON file for external consumption."""
        if output_file is None:
            output_file = self.env_config.get_log_path(f"unified_events_{self.env}.json")
        
        events = self.get_unified_event_stream(limit)
        
        try:
            with open(output_file, 'w') as f:
                json.dump(events, f, indent=2, default=str)
            
            return output_file
            
        except Exception as e:
            print(f"Error exporting events: {e}")
            return ""
    
    def get_learning_data(self) -> Dict[str, Any]:
        """Get data formatted for learning algorithms."""
        return {
            "deployment_success_rate": self._calculate_success_rate(),
            "healing_effectiveness": self._calculate_healing_effectiveness(),
            "system_stability": self._calculate_stability_score(),
            "recent_events": self.get_unified_event_stream(50),
            "environment": self.env,
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    def _calculate_success_rate(self) -> float:
        """Calculate deployment success rate."""
        events = self.read_deployment_logs(100)
        if not events:
            return 1.0
        
        successful = len([e for e in events if e["status"] == "success"])
        return successful / len(events)
    
    def _calculate_healing_effectiveness(self) -> float:
        """Calculate healing effectiveness."""
        events = self.read_healing_logs(100)
        if not events:
            return 1.0
        
        successful = len([e for e in events if e["status"] == "success"])
        return successful / len(events)
    
    def _calculate_stability_score(self) -> float:
        """Calculate system stability score."""
        issues = self.read_issue_logs(100)
        deployments = self.read_deployment_logs(100)
        
        if not deployments:
            return 1.0
        
        # Stability = (1 - issue_rate) * deployment_success_rate
        issue_rate = len(issues) / max(len(deployments), 1)
        success_rate = self._calculate_success_rate()
        
        return max(0.0, (1 - min(issue_rate, 1.0)) * success_rate)
    
    def _get_infra_health(self) -> Dict[str, Any]:
        """Get current infrastructure health status."""
        try:
            health_log = self.env_config.get_log_path('infra_health_log.csv')
            if os.path.exists(health_log):
                df = pd.read_csv(health_log)
                if not df.empty:
                    latest = df.iloc[-1]
                    return {
                        "cpu_usage": float(latest.get('cpu_usage', 0)),
                        "memory_usage": float(latest.get('memory_usage', 0)),
                        "disk_usage": float(latest.get('disk_usage', 0)),
                        "healthy": bool(latest.get('healthy', True)),
                        "timestamp": latest.get('timestamp', '')
                    }
        except Exception:
            pass
        return {"status": "unavailable"}
    
    def _get_scaling_decisions(self) -> Dict[str, Any]:
        """Get recent scaling decisions."""
        try:
            scaling_log = self.env_config.get_log_path('scaling_decisions.csv')
            if os.path.exists(scaling_log):
                df = pd.read_csv(scaling_log)
                if not df.empty:
                    recent = df.tail(5).to_dict('records')
                    return {
                        "recent_decisions": recent,
                        "current_workers": int(df.iloc[-1].get('workers', 1)),
                        "last_action": df.iloc[-1].get('action', 'none')
                    }
        except Exception:
            pass
        return {"current_workers": 1, "last_action": "none"}
    
    def _get_cluster_load(self) -> Dict[str, Any]:
        """Get current cluster load metrics."""
        try:
            queue_log = self.env_config.get_log_path('queue_monitor.csv')
            if os.path.exists(queue_log):
                df = pd.read_csv(queue_log)
                if not df.empty:
                    latest = df.iloc[-1]
                    return {
                        "queue_depth": int(latest.get('queue_size', 0)),
                        "throughput": float(latest.get('throughput', 0)),
                        "active_workers": int(latest.get('active_workers', 1)),
                        "load_percentage": float(latest.get('load_percentage', 0))
                    }
        except Exception:
            pass
        return {"queue_depth": 0, "throughput": 0, "active_workers": 1}

# Global API adapter instances
_api_adapters = {}

def get_api_adapter(env='dev') -> APIAdapter:
    """Get or create API adapter for environment."""
    global _api_adapters
    if env not in _api_adapters:
        _api_adapters[env] = APIAdapter(env)
    return _api_adapters[env]