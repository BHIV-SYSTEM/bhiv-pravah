"""
Safe Orchestrator - Executes RL decisions with safety validation
DEMO_MODE Execution Gate: Enforces RL-only action intake with prod-level safety
"""

import datetime
import json
import os
from typing import Dict, Any, List, Optional

from contracts.decision_contract import DecisionContract, validate_decision_contract
from contracts.execution_contract import (
    advance_execution_state,
    build_execution_contract,
    validate_execution_contract,
)
from contracts.runtime_attestation import compute_runtime_attestation

def get_safe_executor(env='dev'):
    """Get safe executor instance"""
    return SafeOrchestrator(env)

class SafeOrchestrator:
    def __init__(self, env='dev'):
        self.env = env
        self._service_state: Dict[str, Dict[str, Any]] = {}
        self.safe_actions = {
            'restart': self._restart_service,
            'scale_up': self._scale_up_service,
            'noop': self._no_operation,
            'scale_down': self._scale_down_service,
            'rollback': self._rollback_deployment
        }
        
        # Environment-specific safety rules
        self.safety_rules = {
            'prod': ['noop', 'restart'],  # Production frozen mode: noop-first, restart only
            'stage': ['restart', 'noop'],  # Stage allows restart and noop
            'dev': ['restart', 'scale_up', 'noop', 'scale_down']  # Dev allows most actions
        }
        
        # Load DEMO_MODE configuration
        try:
            from demo_mode_config import is_demo_mode_active, DEMO_ENFORCE_PROD_SAFETY
            self.demo_mode = is_demo_mode_active()
            self.demo_enforce_prod = DEMO_ENFORCE_PROD_SAFETY
        except ImportError:
            self.demo_mode = False
            self.demo_enforce_prod = False

    def _build_refusal_result(
        self,
        action_requested: str,
        reason: str,
        reason_code: str,
        source: Optional[str],
        timestamp: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build standardized refusal response payload."""
        result = {
            'action_requested': action_requested,
            'action_executed': 'noop',
            'success': False,
            'refused': True,
            'reason': reason,
            'reason_code': reason_code,
            'timestamp': timestamp or datetime.datetime.now().isoformat(),
            'source': source
        }
        if extra:
            result.update(extra)
        return result

    def _log_decision(self, action_requested: str, result: Dict[str, Any], context: Dict[str, Any], source: Optional[str]):
        """Structured, timestamped, environment-aware decision log."""
        log_dir = os.path.join('logs', self.env)
        os.makedirs(log_dir, exist_ok=True)
        decision_log_file = os.path.join(log_dir, 'orchestrator_decisions.jsonl')

        decision_entry = {
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'environment': self.env,
            'source': source or 'unknown',
            'action_requested': action_requested,
            'action_executed': result.get('action_executed', 'noop'),
            'success': bool(result.get('success', False)),
            'refused': bool(result.get('refused', False)),
            'reason': result.get('reason'),
            'reason_code': result.get('reason_code'),
            'context': {
                'app_name': context.get('app_name'),
                'event_type': context.get('event_type')
            },
            'result': result
        }

        with open(decision_log_file, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(decision_entry) + '\n')
    
    def is_action_safe(self, action: str) -> bool:
        """Check if action is safe for current environment"""
        allowed_actions = self.safety_rules.get(self.env, ['noop'])
        return action in allowed_actions
    
    def execute_safe_action(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action if safe, otherwise default to noop"""
        timestamp = datetime.datetime.now().isoformat()
        
        if not self.is_action_safe(action):
            # Log safety violation and default to noop
            result = {
                'action_requested': action,
                'action_executed': 'noop',
                'reason': f'Action {action} not safe for {self.env} environment',
                'success': True,
                'timestamp': timestamp,
                'safety_override': True
            }
            self._log_execution(result)
            return result
        
        # Execute the safe action
        try:
            execution_func = self.safe_actions.get(action, self._no_operation)
            result = execution_func(context)
            result.update({
                'action_executed': action,
                'success': result.get('success', True),
                'timestamp': timestamp,
                'safety_override': False,
                'confidence': 1.0  # Explicit confidence for arbitration
            })
        except Exception as e:
            result = {
                'action_executed': action,
                'success': False,
                'error': str(e),
                'timestamp': timestamp,
                'safety_override': False
            }
        
        self._log_execution(result)
        return result
    
    def _validate_demo_mode_gate(self, source: Optional[str], action: str) -> tuple[bool, str]:
        """
        DEMO_MODE execution gate - block direct calls, validate RL intake
        
        Args:
            source: Source identifier (should be 'rl_decision_layer' in DEMO_MODE)
            action: Action being requested
            
        Returns:
            Tuple of (allowed, reason) - (True, "") if allowed, (False, reason) if blocked
        """
        from control_plane.core.proof_logger import write_proof, ProofEvents
        
        if not self.demo_mode:
            return (True, "")  # Not in demo mode, allow through
        
        # Check if action came from RL layer
        if not source or source not in ['rl_decision_layer', 'rl_intake_gate']:
            write_proof(ProofEvents.DEMO_MODE_BLOCK, {
                'env': self.env,
                'action': action,
                'source': source or 'UNKNOWN',
                'reason': 'Direct orchestrator call blocked - must come through RL intake gate',
                'demo_mode': True
            })
            return (False, "DEMO_MODE: Direct calls blocked - actions must come from RL layer")
        
        # Validate RL intake source
        write_proof(ProofEvents.RL_INTAKE_VALIDATED, {
            'env': self.env,
            'action': action,
            'source': source,
            'status': 'validated'
        })
        
        return (True, "")
    
    def _enforce_demo_safety(self, action: str, source: Optional[str]) -> tuple[bool, str]:
        """
        Enforce DEMO_MODE production-level safety rules
        
        Args:
            action: Action to validate
            source: Source identifier
            
        Returns:
            Tuple of (safe, reason) - (True, "") if safe, (False, reason) if refused
        """
        from control_plane.core.prod_safety import is_demo_mode_safe
        from control_plane.core.proof_logger import write_proof, ProofEvents
        
        is_safe, refusal_reason = is_demo_mode_safe(action, source)
        
        if not is_safe:
            write_proof(ProofEvents.UNSAFE_ACTION_REFUSED, {
                'env': self.env,
                'action': action,
                'source': source or 'UNKNOWN',
                'reason': refusal_reason,
                'demo_mode': self.demo_mode
            })
        
        return (is_safe, refusal_reason)
    
    def execute_action(self, action: str, context: Dict[str, Any], source: Optional[str] = None) -> Dict[str, Any]:
        """
        CENTRALIZED EXECUTION GATE - All action execution passes through here
        
        This is the ONLY entry point for action execution in DEMO_MODE.
        ALL paths must pass through:
        1. RL decision intake validation
        2. Safety guard checks
        3. Determinism verification
        
        Args:
            action: Action name to execute
            context: Execution context
            source: Source identifier (required in DEMO_MODE)
            
        Returns:
            Execution result with status and proof logging
        """
        from control_plane.core.proof_logger import write_proof, ProofEvents
        timestamp = datetime.datetime.now().isoformat()
        execution_contract_data = context.get('execution_contract')
        execution_contract = None

        if execution_contract_data:
            execution_contract = validate_execution_contract(execution_contract_data, context)

        emergency_freeze_enabled = str(os.getenv('EMERGENCY_FREEZE_ENABLED', 'false')).lower() == 'true'
        emergency_freeze_reason = os.getenv('EMERGENCY_FREEZE_REASON', '').strip() or 'manual_override'
        app_name = context.get('app_name', 'unknown')

        try:
            from control_plane.app_override_manager import AppOverrideManager
            app_override = AppOverrideManager().get_app_override(app_name)
        except Exception:
            app_override = None

        if app_override and app_override.get('freeze_enabled') and action != 'noop':
            result = self._build_refusal_result(
                action_requested=action,
                reason=f"Manual app freeze active for {app_name}: {app_override.get('reason', 'manual_override')}",
                reason_code='app_manual_freeze_override',
                source=source,
                timestamp=timestamp,
                extra={
                    'app_manual_freeze': True,
                    'app_name': app_name,
                    'freeze_reason': app_override.get('reason'),
                    'freeze_until': app_override.get('freeze_until')
                }
            )
            write_proof(ProofEvents.ORCH_REFUSE, {
                'env': self.env,
                'action': action,
                'reason': 'app_manual_freeze_override',
                'app_name': app_name,
                'freeze_reason': app_override.get('reason'),
                'status': 'refused',
                'source': source
            })
            self._log_decision(action, result, context, source)
            return result

        decision = validate_decision_contract({
            'decision_type': 'execution',
            'action': action,
            'parameters': {
                'app_name': app_name,
                'source': source or 'legacy',
            },
            'version': 'v1',
        })
        return self.execute_decision_contract(decision, context, source=source)

    def execute_decision_contract(
        self,
        decision: DecisionContract | dict,
        context: Dict[str, Any],
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        from control_plane.core.proof_logger import write_proof, ProofEvents
        from control_plane.core.action_governance import ActionGovernance

        try:
            if not isinstance(decision, DecisionContract):
                decision = validate_decision_contract(decision)
        except Exception as exc:
            return self._build_refusal_result(
                action_requested=str(getattr(decision, 'action', 'invalid')),
                reason=str(exc),
                reason_code='invalid_decision_contract',
                source=source,
                extra={'decision_validation_error': str(exc)},
            )

        contract_context = {
            **context,
            "decision_type": decision.decision_type,
            "decision_version": decision.version,
            "decision_parameters": decision.parameters,
        }

        governance = ActionGovernance(env=self.env)
        governance_decision = governance.evaluate_contract(
            decision=decision,
            context=contract_context,
            source=source,
        )

        if governance_decision.should_block:
            return self._build_refusal_result(
                action_requested=decision.action,
                reason=governance_decision.details.get('message', governance_decision.reason),
                reason_code=governance_decision.reason,
                source=source,
                extra={
                    'governance_blocked': True,
                    'governance_reason': governance_decision.reason,
                    'details': governance_decision.details,
                },
            )

        trusted_signers = governance.get_policy_engine().trusted_signers
        approved_by = contract_context.get('approved_by') or (
            source if source in trusted_signers else 'sarathi'
        )
        # Attach governance policy snapshot (if present) so executions are attestable
        policy_snapshot = None
        try:
            policy_snapshot = {
                'policy_id': getattr(governance_decision, 'policy_id', None),
                'policy_version': getattr(governance_decision, 'policy_version', None),
                'policy_hash': getattr(governance_decision, 'policy_hash', None),
            }
        except Exception:
            policy_snapshot = None

        # Compute a deterministic runtime attestation (software-rooted)
        try:
            runtime_attestation = compute_runtime_attestation(manifest=None, environment=None)
        except Exception:
            runtime_attestation = None

        execution_contract = build_execution_contract(
            decision_contract=decision,
            execution_payload=contract_context,
            approved_by=approved_by,
            policy_snapshot=policy_snapshot,
            runtime_attestation=runtime_attestation.model_dump() if runtime_attestation is not None else None,
        )

        try:
            from control_plane.security.deterministic_policy_engine import PolicyAdmissionRequest

            policy_engine = governance.get_policy_engine()
            governance_contract = governance.build_governance_contract(context=contract_context, governance_approver=approved_by)
            policy_engine.enforce(
                PolicyAdmissionRequest(
                    action=decision.action,
                    context={
                        **contract_context,
                        "env": self.env,
                        "execution_payload": execution_contract.execution_payload,
                    },
                    policy_version=decision.version,
                    runtime_policy_version=governance.POLICY_VERSION,
                    governance_contract=governance_contract,
                    decision_contract=decision,
                    execution_contract=execution_contract,
                    policy_id=governance.POLICY_ID,
                )
            )
        except Exception as exc:
            return self._build_refusal_result(
                action_requested=decision.action,
                reason=str(exc),
                reason_code='deterministic_policy_rejection',
                source=source,
                extra={
                    'policy_enforcement_error': str(exc),
                },
            )

        contract_context = {
            **contract_context,
            'execution_id': execution_contract.execution_id,
            'execution_contract': execution_contract.model_dump(mode='json'),
        }

        action = decision.action
        context = contract_context
        timestamp = datetime.datetime.now().isoformat()
        emergency_freeze_enabled = str(os.getenv('EMERGENCY_FREEZE_ENABLED', 'false')).lower() == 'true'
        emergency_freeze_reason = os.getenv('EMERGENCY_FREEZE_REASON', '').strip() or 'manual_override'

        if emergency_freeze_enabled and action != 'noop':
            result = self._build_refusal_result(
                action_requested=action,
                reason=f'Emergency freeze active: {emergency_freeze_reason}',
                reason_code='emergency_freeze_override',
                source=source,
                timestamp=timestamp,
                extra={
                    'emergency_freeze': True,
                    'freeze_reason': emergency_freeze_reason
                }
            )
            write_proof(ProofEvents.ORCH_REFUSE, {
                'env': self.env,
                'action': action,
                'reason': 'emergency_freeze_override',
                'freeze_reason': emergency_freeze_reason,
                'status': 'refused',
                'source': source
            })
            self._log_decision(action, result, context, source)
            return result

        if action not in self.safe_actions:
            result = self._build_refusal_result(
                action_requested=action,
                reason=f'Illegal action requested: {action}',
                reason_code='illegal_action',
                source=source,
                timestamp=timestamp
            )
            write_proof(ProofEvents.ORCH_REFUSE, {
                'env': self.env,
                'action': action,
                'reason': 'illegal_action',
                'status': 'refused',
                'source': source
            })
            self._log_decision(action, result, context, source)
            return result
        
        # GATE 1: DEMO_MODE intake validation
        gate_passed, gate_reason = self._validate_demo_mode_gate(source, action)
        if not gate_passed:
            result = self._build_refusal_result(
                action_requested=action,
                reason=gate_reason,
                reason_code='demo_mode_gate_blocked',
                source=source,
                timestamp=timestamp,
                extra={'demo_mode_blocked': True}
            )
            self._log_decision(action, result, context, source)
            return result
        
        # GATE 2: DEMO_MODE safety enforcement
        if self.demo_mode and self.demo_enforce_prod:
            safety_passed, safety_reason = self._enforce_demo_safety(action, source)
            if not safety_passed:
                result = self._build_refusal_result(
                    action_requested=action,
                    reason=safety_reason,
                    reason_code='demo_safety_refused',
                    source=source,
                    timestamp=timestamp,
                    extra={'safety_refused': True}
                )
                self._log_decision(action, result, context, source)
                return result
        
        # GATE 3: Environment-specific safety check
        if not self.is_action_safe(action):
            write_proof(ProofEvents.ORCH_REFUSE, {
                'env': self.env,
                'action': action,
                'reason': 'environment_safety_rules',
                'status': 'refused'
            })
            result = self._build_refusal_result(
                action_requested=action,
                reason=f'Action {action} not safe for {self.env} environment',
                reason_code='environment_safety_rules',
                source=source,
                timestamp=timestamp,
                extra={'safety_override': True}
            )
            self._log_decision(action, result, context, source)
            return result
        
        # GATE 4: Action Governance Check (eligibility, cooldowns, repetition)
        from control_plane.core.action_governance import ActionGovernance
        
        governance = ActionGovernance(env=self.env)
        governance_decision = governance.evaluate_action(
            action=action,
            context=context,
            source=source
        )
        
        if governance_decision.should_block:
            # Log specific governance event based on reason
            from control_plane.core.action_governance import GovernanceReason
            
            event_map = {
                GovernanceReason.COOLDOWN_ACTIVE.value: ProofEvents.COOLDOWN_ACTIVE,
                GovernanceReason.REPETITION_LIMIT_EXCEEDED.value: ProofEvents.REPETITION_SUPPRESSED,
                GovernanceReason.ACTION_NOT_ELIGIBLE.value: ProofEvents.ACTION_ELIGIBILITY_FAILED,
                GovernanceReason.PREREQUISITE_NOT_MET.value: ProofEvents.ACTION_ELIGIBILITY_FAILED,
            }
            
            specific_event = event_map.get(
                governance_decision.reason,
                ProofEvents.GOVERNANCE_BLOCK
            )
            
            write_proof(specific_event, {
                'env': self.env,
                'action': action,
                'block_reason': governance_decision.reason,
                'details': governance_decision.details,
                'self_imposed': True,
                'source': source
            })
            
            result = self._build_refusal_result(
                action_requested=action,
                reason=governance_decision.details.get('message', governance_decision.reason),
                reason_code=governance_decision.reason,
                source=source,
                timestamp=timestamp,
                extra={
                    'governance_blocked': True,
                    'governance_reason': governance_decision.reason,
                    'details': governance_decision.details
                }
            )
            self._log_decision(action, result, context, source)
            return result
        
        # All gates passed - log and execute
        write_proof(ProofEvents.EXECUTION_GATE_PASSED, {
            'env': self.env,
            'action': action,
            'source': source or 'legacy',
            'demo_mode': self.demo_mode,
            'gates_passed': ['rl_intake', 'demo_safety', 'env_safety', 'governance']
        })
        
        # Execute the action
        try:
            execution_func = self.safe_actions.get(action, self._no_operation)
            result = execution_func(context)
            result.update({
                'action_executed': action,
                'success': result.get('success', True),
                'timestamp': timestamp,
                'safety_override': False,
                'source': source
            })

            if execution_contract:
                execution_contract = advance_execution_state(execution_contract, 'EXECUTED')
                execution_contract = advance_execution_state(
                    execution_contract,
                    'COMPLETED' if result.get('success', True) else 'FAILED',
                )
                result.update({
                    'execution_id': execution_contract.execution_id,
                    'execution_hash': execution_contract.execution_hash,
                    'approved_at': execution_contract.approved_at,
                    'approved_by': execution_contract.approved_by,
                    'immutable': execution_contract.immutable,
                    'execution_state': execution_contract.execution_state,
                    'execution_state_history': list(execution_contract.execution_state_history),
                    'execution_contract': execution_contract.model_dump(mode='json'),
                })
            
            write_proof(ProofEvents.ORCH_EXEC, {
                'env': self.env,
                'action': action,
                'status': 'executed',
                'source': source
            })
            
            write_proof(ProofEvents.SYSTEM_STABLE, {
                'env': self.env,
                'recovery_action': action,
                'status': 'stable'
            })
            
        except Exception as e:
            result = {
                'action_executed': action,
                'success': False,
                'error': str(e),
                'timestamp': timestamp,
                'safety_override': False,
                'source': source
            }

        self._log_decision(action, result, context, source)
        
        return result
    
    def validate_and_execute(self, action_index: int, context: Dict[str, Any], source: Optional[str] = None) -> Dict[str, Any]:
        """Validate and execute action by index - routes through centralized execute_action()"""
        
        # Map action indices to action names
        action_map = {
            0: 'noop',
            1: 'restart',
            2: 'scale_up', 
            3: 'scale_down',
            4: 'rollback'
        }
        
        if action_index not in action_map:
            timestamp = datetime.datetime.now().isoformat()
            result = self._build_refusal_result(
                action_requested=f'action_index:{action_index}',
                reason=f'Illegal action index requested: {action_index}',
                reason_code='illegal_action_index',
                source=source,
                timestamp=timestamp,
                extra={'action_index': action_index}
            )
            from control_plane.core.proof_logger import write_proof, ProofEvents
            write_proof(ProofEvents.ORCH_REFUSE, {
                'env': self.env,
                'action': f'action_index:{action_index}',
                'reason': 'illegal_action_index',
                'status': 'refused',
                'source': source
            })
            self._log_decision(f'action_index:{action_index}', result, context, source)
            return result

        action_name = action_map[action_index]
        
        # Route through centralized execution gate
        return self.execute_action(action_name, context, source=source)

    def _get_service_state(self, app_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get or initialize simulated service state for realistic action execution."""
        if app_name not in self._service_state:
            initial_replicas = int(context.get('replicas', context.get('workers', 1)) or 1)
            self._service_state[app_name] = {
                'replicas': max(initial_replicas, 1),
                'restart_count': 0,
                'last_action': 'init',
                'last_updated': datetime.datetime.now().isoformat()
            }
        return self._service_state[app_name]

    def _update_service_state(self, app_name: str, state: Dict[str, Any], action: str):
        """Persist updated simulated service state."""
        state['last_action'] = action
        state['last_updated'] = datetime.datetime.now().isoformat()
        self._service_state[app_name] = state
    
    def _restart_service(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Restart service action (simulated but operationally realistic)."""
        app_name = context.get('app_name', 'unknown')
        service_state = self._get_service_state(app_name, context)

        if context.get('simulate_failure') is True:
            return {
                'action': 'restart',
                'app_name': app_name,
                'success': False,
                'details': f'Restart failed for {app_name}: simulated restart timeout',
                'error_type': 'restart_timeout',
                'adapter': 'simulated_devops',
                'duration_ms': 15000
            }

        service_state['restart_count'] += 1
        self._update_service_state(app_name, service_state, 'restart')

        return {
            'action': 'restart',
            'app_name': app_name,
            'success': True,
            'details': f'Service {app_name} restarted successfully',
            'recovery_time': '15s',
            'command': f'systemctl restart {app_name}',
            'restart_count': service_state['restart_count'],
            'adapter': 'simulated_devops',
            'duration_ms': 15000
        }
    
    def _scale_up_service(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Scale up service action (simulated but with realistic constraints)."""
        app_name = context.get('app_name', 'unknown')
        service_state = self._get_service_state(app_name, context)
        current_replicas = int(service_state.get('replicas', 1) or 1)
        max_replicas = int(context.get('max_replicas', 5) or 5)

        if current_replicas >= max_replicas:
            return {
                'action': 'scale_up',
                'app_name': app_name,
                'success': False,
                'replicas_before': current_replicas,
                'replicas_after': current_replicas,
                'details': f'Scale up skipped: {app_name} already at max replicas ({max_replicas})',
                'error_type': 'capacity_limit',
                'adapter': 'simulated_devops',
                'duration_ms': 2000
            }

        new_replicas = current_replicas + 1
        service_state['replicas'] = new_replicas
        self._update_service_state(app_name, service_state, 'scale_up')
        
        return {
            'action': 'scale_up',
            'app_name': app_name,
            'success': True,
            'replicas_before': current_replicas,
            'replicas_after': new_replicas,
            'details': f'Scaled {app_name} from {current_replicas} to {new_replicas} replicas',
            'command': f'kubectl scale deployment/{app_name} --replicas={new_replicas}',
            'adapter': 'simulated_devops',
            'duration_ms': 2000
        }
    
    def _scale_down_service(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Scale down service action (simulated but with floor guardrails)."""
        app_name = context.get('app_name', 'unknown')
        service_state = self._get_service_state(app_name, context)
        current_replicas = int(service_state.get('replicas', context.get('replicas', 2)) or 2)
        min_replicas = int(context.get('min_replicas', 1) or 1)

        if current_replicas <= min_replicas:
            return {
                'action': 'scale_down',
                'app_name': app_name,
                'success': False,
                'replicas_before': current_replicas,
                'replicas_after': current_replicas,
                'details': f'Scale down skipped: {app_name} already at minimum replicas ({min_replicas})',
                'error_type': 'minimum_capacity_guard',
                'adapter': 'simulated_devops',
                'duration_ms': 2000
            }

        new_replicas = current_replicas - 1
        service_state['replicas'] = new_replicas
        self._update_service_state(app_name, service_state, 'scale_down')
        
        return {
            'action': 'scale_down',
            'app_name': app_name,
            'success': True,
            'replicas_before': current_replicas,
            'replicas_after': new_replicas,
            'details': f'Scaled {app_name} from {current_replicas} to {new_replicas} replicas',
            'command': f'kubectl scale deployment/{app_name} --replicas={new_replicas}',
            'adapter': 'simulated_devops',
            'duration_ms': 2000
        }
    
    def _no_operation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """No operation - safe default"""
        return {
            'action': 'noop',
            'details': 'No action taken - system monitoring continues',
            'reason': 'Safe default or false alarm detected'
        }
    
    def _rollback_deployment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Rollback to previous deployment"""
        app_name = context.get('app_name', 'unknown')
        return {
            'action': 'rollback',
            'app_name': app_name,
            'details': f'Rolled back {app_name} to previous stable version',
            'rollback_time': '45s'
        }
    
    def _log_execution(self, result: Dict[str, Any]):
        """Log execution result"""
        log_dir = f"logs/{self.env}"
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, "orchestrator_executions.log")
        with open(log_file, 'a') as f:
            f.write(json.dumps(result) + '\n')