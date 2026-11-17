
"""
State Adapter
Converts heterogeneous Agent State into normalized RL Observation.
"""

from typing import Dict, Any, List

class StateAdapter:
    """
    Adapter to convert Agent Runtime Context into RL-consumable state.
    BRIDGE: Agent Internal State -> RL Observation Schema
    """
    
    def __init__(self, env='dev'):
        self.env = env
        
    def adapt_state(self, 
                   event: Dict[str, Any], 
                   agent_state: str,
                   memory_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert internal Agent Runtime state into Ritesh's expected flat RL schema.
        
        Required Fields:
            app, env, event_type, state, latency_ms, errors_last_min, workers
        """
        # Robust metrics extraction - look in data or top level
        data = event.get('data', {})
        metrics = event.get('metrics', {}) or data.get('metrics', {})
        
        # 1. Map to flat schema
        rl_request = {
            "app": event.get("app_id") or event.get("app_name") or "unknown-app",
            "env": self.env,
            "event_type": event.get("event_type", "unknown"),
            "state": agent_state.lower(),
            "latency_ms": float(metrics.get("latency_ms") or event.get("latency_ms") or data.get("latency_ms") or 0.0),
            "errors_last_min": int(metrics.get("errors_last_min") or metrics.get("error_rate", 0) * 10 or 0),
            "workers": int(event.get("workers") or metrics.get("workers") or 3)
        }
        
        # 2. Log normalization event
        from control_plane.core.proof_logger import write_proof, ProofEvents
        write_proof(ProofEvents.RL_INPUT, {
            "mapped_payload": rl_request,
            "original_event_type": event.get("event_type")
        })
        
        return rl_request

    def _normalize_metrics(self, metrics: Dict[str, Any]) -> Dict[str, float]:
        """Ensure metrics are floats and handle missing values."""
        normalized = {}
        target_keys = {
            'cpu_percent': ['cpu_percent', 'cpu', 'cpu_usage'],
            'memory_percent': ['memory_percent', 'memory', 'memory_usage'],
            'error_rate': ['error_rate', 'errors', 'failure_rate']
        }
        
        for norm_key, source_keys in target_keys.items():
            val = 0.0
            for key in source_keys:
                if key in metrics:
                    val = metrics[key]
                    break
            
            try:
                normalized[norm_key] = float(val)
            except (ValueError, TypeError):
                normalized[norm_key] = 0.0
                
        return normalized

    def to_vector(self, rl_request: Dict[str, Any]) -> List[float]:
        """
        Future-proofing: Convert dictionary state to vector [0..1]
        for neural network models.
        """
        # Example vectorization
        metrics = rl_request.get('metrics', {})
        return [
            metrics.get('cpu_percent', 0) / 100.0,
            metrics.get('memory_percent', 0) / 100.0,
            metrics.get('error_rate', 0)
        ]
