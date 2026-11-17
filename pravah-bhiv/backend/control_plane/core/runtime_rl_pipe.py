#!/usr/bin/env python3
"""
Runtime → RL Direct Pipe
Pipes normalized runtime JSON to Ritesh's RL layer unchanged and live
"""

import json
import os
from datetime import datetime
from control_plane.core.env_config import EnvironmentConfig
from control_plane.core.rl_remote_client import RLRemoteClient
from control_plane.core.state_adapter import StateAdapter
from contracts.decision_contract import validate_decision_contract

class RuntimeRLPipe:
    """Direct pipe from runtime events to the remote RL Decision Brain."""
    
    def __init__(self, env='dev'):
        self.env = env
        self.env_config = EnvironmentConfig(env)
        self.autonomy_gates = {
            'decisions_enabled': bool(self.env_config.get('autonomy_decisions_enabled', True)),
            'learning_enabled': bool(self.env_config.get('autonomy_learning_enabled', env == 'dev'))
        }
        # Use the remote RL client
        self.rl_brain = RLRemoteClient()
        self.state_adapter = StateAdapter(env)
        
    def get_decision(self, event_data: dict, agent_state: str = "unknown", memory_context: dict = None) -> dict:
        """
        Get RL decision WITHOUT executing it (Pure sensing/deciding).
        Used by the Arbitrator.
        """
        # Strict validation (same as pipe)
        from control_plane.core.runtime_event_validator import validate_and_log_payload
        is_valid, validated_payload, error_msg = validate_and_log_payload(event_data, "RL_INPUT_QUERY")
        
        if not is_valid:
            return {'action': 'noop', 'confidence': 1.0, 'reason': error_msg}

        if not self.autonomy_gates['decisions_enabled']:
            return {
                'action': 'noop',
                'confidence': 1.0,
                'reason': f'autonomy_gate: decisions disabled in {self.env}',
                'source': 'autonomy_gate',
                'learning_enabled': self.autonomy_gates['learning_enabled']
            }
            
        # Adapt Agent State -> RL State
        rl_request = self.state_adapter.adapt_state(
            event=validated_payload,
            agent_state=agent_state,
            memory_context=memory_context or {}
        )

        # Get RL decision
        decision_response = self.rl_brain.decide(rl_request)
        action_str = decision_response.get("action", "noop")
        source = decision_response.get("source", "rl_brain")

        try:
            decision_contract = validate_decision_contract({
                "decision_type": "execution",
                "action": action_str,
                "parameters": {
                    "service_id": validated_payload.get("app", "unknown-service"),
                },
                "version": decision_response["version"],
            })
        except Exception as exc:
            return {
                'rl_action': 0,
                'execution': {'status': 'refused'},
                'validation_error': str(exc),
                'brain_metadata': decision_response,
            }
        
        # PROOF: Explicitly log if we hit a fallback (No Silent Failures)
        if source == "remote_client_fallback":
            from control_plane.core.proof_logger import write_proof, ProofEvents
            write_proof(ProofEvents.RL_DECISION, {
                "env": self.env,
                "status": "failed",
                "reason": decision_response.get("reason"),
                "fallback_action": "noop",
                "source": "rl_brain_fallback"
            })
        
        return {
            "action": action_str,
            "confidence": decision_response.get("confidence", 0.8), 
            "brain_response": decision_response,
            "source": "rl_brain",
            "learning_enabled": self.autonomy_gates['learning_enabled'],
            "rl_state_vector": self.state_adapter.to_vector(rl_request) # Feature logging
        }

    def pipe_runtime_event(self, event_data: dict, agent_state: str = "unknown", memory_context: dict = None) -> dict:
        """Pipe runtime event to RL Brain with structured proof logging and validation."""
        
        # Strict validation BEFORE calling RL
        from control_plane.core.runtime_event_validator import validate_and_log_payload
        from control_plane.core.proof_logger import write_proof, ProofEvents
        
        is_valid, validated_payload, error_msg = validate_and_log_payload(event_data, "RL_INPUT")
        
        if not is_valid:
            # (validation error logic unchanged)
            # ...
            return {
                'rl_action': 0,
                'execution': {'status': 'refused'}, # Simplified for brevity in replace
                'validation_error': error_msg
            }
        
        # Structured proof logging - RL_CONSUME
        write_proof(ProofEvents.RL_CONSUME, {
            'env': self.env,
            'event_type': validated_payload.get('event_type'),
            'payload': validated_payload,
            'status': 'consumed'
        })
        
        # Log payload before RL (unchanged pass-through)
        from control_plane.core.runtime_event_validator import RuntimeEventValidator
        RuntimeEventValidator.log_payload_integrity(validated_payload, "RL_CONSUME")
        
        # Adapt State
        rl_request = self.state_adapter.adapt_state(
            event=validated_payload,
            agent_state=agent_state,
            memory_context=memory_context or {}
        )

        # Get RL decision
        decision_response = self.rl_brain.decide(rl_request)
        action_str = decision_response.get("action", "noop")

        try:
            decision_contract = validate_decision_contract({
                "decision_type": "execution",
                "action": action_str,
                "parameters": {
                    "service_id": validated_payload.get("app", "unknown-service"),
                },
                "version": decision_response["version"],
            })
        except Exception as exc:
            return {
                'rl_action': 0,
                'execution': {'status': 'refused'},
                'validation_error': str(exc),
                'brain_metadata': decision_response,
            }

        # Map action string to integer for compatibility with existing orchestrator logic
        # 0: noop, 1: restart, 2: scale_up, 3: scale_down, 4: rollback
        action_map = {
            "noop": 0,
            "restart": 1,
            "scale_up": 2,
            "scale_down": 3,
            "rollback": 4
        }
        rl_action_int = action_map.get(decision_contract.action, 0)

        # Structured proof logging - RL_DECISION
        write_proof(ProofEvents.RL_DECISION, {
            'env': self.env,
            'event_type': validated_payload.get('event_type'),
            'payload': validated_payload,
            'decision': rl_action_int,
            'decision_str': action_str,
            'brain_response': decision_response,
            'decision_contract': decision_contract.model_dump(),
            'status': 'decided'
        })
        
        # Safe execution validation
        from control_plane.core.rl_orchestrator_safe import get_safe_executor
        safe_executor = get_safe_executor(self.env)
        
        # Validate and execute (or refuse)
        # We pass the integer action as expected by validate_and_execute
        execution_result = safe_executor.execute_decision_contract(
            decision_contract,
            validated_payload,
            source='rl_decision_layer'
        )
        
        return {
            'rl_action': rl_action_int,
            'action_str': action_str,
            'decision_contract': decision_contract.model_dump(),
            'execution': execution_result,
            'brain_metadata': decision_response
        }

    def build_execution_feedback_payload(
        self,
        decision: dict,
        execution_result: dict,
        context: dict = None
    ) -> dict:
        """Build a normalized feedback payload for RL from execution outcome."""
        context = context or {}
        requested_action = decision.get('action_name') or decision.get('action') or 'noop'
        executed_action = execution_result.get('action_executed', requested_action)
        was_success = bool(execution_result.get('success'))

        reward = 1.0 if was_success else -1.0

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'env': self.env,
            'app_id': context.get('app_name') or decision.get('input_data', {}).get('app_id', 'unknown'),
            'event_type': context.get('event_type') or decision.get('input_data', {}).get('event_type', 'unknown'),
            'decision': {
                'requested_action': requested_action,
                'source': decision.get('source', 'unknown'),
                'confidence': decision.get('confidence', 0.0)
            },
            'execution': {
                'executed_action': executed_action,
                'success': was_success,
                'reason': execution_result.get('reason'),
                'error': execution_result.get('error'),
                'adapter': execution_result.get('adapter'),
                'duration_ms': execution_result.get('duration_ms')
            },
            'reward': reward
        }

    def send_execution_feedback(self, decision: dict, execution_result: dict, context: dict = None) -> dict:
        """Send execution feedback to RL service (best-effort, non-blocking semantics)."""
        payload = self.build_execution_feedback_payload(decision, execution_result, context=context)
        payload['learning_enabled'] = self.autonomy_gates['learning_enabled']
        payload['decisions_enabled'] = self.autonomy_gates['decisions_enabled']

        log_dir = os.path.join('logs', self.env)
        os.makedirs(log_dir, exist_ok=True)
        feedback_log_file = os.path.join(log_dir, 'rl_execution_feedback.jsonl')
        with open(feedback_log_file, 'a', encoding='utf-8') as feedback_file:
            feedback_file.write(json.dumps(payload) + '\n')

        if not self.autonomy_gates['learning_enabled']:
            return {
                'payload': payload,
                'delivery': {
                    'delivered': False,
                    'reason': f'autonomy_gate: learning disabled in {self.env}'
                },
                'persisted_locally': True,
                'feedback_log_file': feedback_log_file,
                'learning_enabled': False
            }

        delivery = self.rl_brain.send_execution_feedback(payload)
        return {
            'payload': payload,
            'delivery': delivery,
            'persisted_locally': True,
            'feedback_log_file': feedback_log_file,
            'learning_enabled': True
        }

# Global RL pipe instances per environment
_rl_pipes = {}

def get_rl_pipe(env='dev'):
    """Get RL pipe instance for specific environment."""
    global _rl_pipes
    if env not in _rl_pipes:
        _rl_pipes[env] = RuntimeRLPipe(env)
    return _rl_pipes[env]