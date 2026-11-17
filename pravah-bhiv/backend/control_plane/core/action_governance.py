"""
Action Governance Module
Implements action eligibility, cooldowns, and repetition suppression.

The agent uses this module to determine when NOT to act, enforcing:
1. Action eligibility rules (prerequisites, allowlists)
2. Cooldown periods (minimum time between repeated actions)
3. Repetition suppression (prevent action loops)
"""
import time
import hashlib
import json
import os
import threading
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from collections import deque
from enum import Enum

from contracts.decision_contract import DecisionContract, validate_decision_contract
from contracts.policy_snapshot import compute_policy_hash, PolicySnapshot
from control_plane.security.deterministic_policy_engine import (
    AdmissionState,
    DeterministicPolicyEngine,
    PolicyAdmissionRequest,
    RejectionCode,
)
from control_plane.persistence import AppendOnlyLog


def normalize_environment(value: str) -> str:
    mapping = {
        "dev": "DEV",
        "stage": "STAGE",
        "staging": "STAGE",
        "prod": "PROD",
        "production": "PROD",
    }
    return mapping[value.strip().lower()]


class GovernanceReason(Enum):
    """Reasons for governance blocking."""
    COOLDOWN_ACTIVE = "cooldown_active"
    REPETITION_LIMIT_EXCEEDED = "repetition_limit_exceeded"
    ACTION_NOT_ELIGIBLE = "action_not_eligible"
    PREREQUISITE_NOT_MET = "prerequisite_not_met"


@dataclass
class GovernanceDecision:
    """Represents an action governance decision."""
    should_block: bool
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    policy_hash: Optional[str] = None
    admission_state: Optional[str] = None
    rejection_code: Optional[str] = None
    legitimacy: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'allowed': not self.should_block,
            'should_block': self.should_block,
            'governance_reason': self.reason,
            'governance_details': self.details,
            'admission_state': self.admission_state,
            'rejection_code': self.rejection_code,
            'legitimacy': self.legitimacy,
            'policy_snapshot': {
                'policy_id': self.policy_id,
                'policy_version': self.policy_version,
                'policy_hash': self.policy_hash,
            },
        }


@dataclass
class ActionRecord:
    """Record of an action execution."""
    action: str
    timestamp: float
    context: Dict[str, Any]


class ActionGovernance:
    """Action governance system for autonomous agents.
    
    Enforces rules about when actions should NOT be executed:
    - Cooldowns: Minimum time between repeated actions
    - Repetition: Prevent action loops
    - Eligibility: Action prerequisites and allowlists
    """
    
    # Default cooldown periods (in seconds) for each action
    DEFAULT_COOLDOWNS = {
        'restart': 60,      # 1 minute between restarts
        'scale_up': 120,    # 2 minutes between scale-ups
        'scale_down': 120,  # 2 minutes between scale-downs
        'rollback': 300,    # 5 minutes between rollbacks
        'noop': 0,          # No cooldown for noop
    }
    
    # Repetition limits: max occurrences within time window
    DEFAULT_REPETITION_LIMIT = 3
    DEFAULT_REPETITION_WINDOW = 300  # 5 minutes
    POLICY_ID = "action_governance_v1"
    POLICY_VERSION = "v1"
    
    def __init__(
        self,
        env: str = 'dev',
        cooldown_periods: Optional[Dict[str, int]] = None,
        repetition_limit: int = DEFAULT_REPETITION_LIMIT,
        repetition_window: int = DEFAULT_REPETITION_WINDOW
    ):
        """Initialize action governance.
        
        Args:
            env: Environment name (dev, stage, prod)
            cooldown_periods: Custom cooldown periods per action
            repetition_limit: Max identical actions within window
            repetition_window: Time window for repetition check (seconds)
        """
        self.env = normalize_environment(env).lower()
        self.cooldown_periods = cooldown_periods or self.DEFAULT_COOLDOWNS
        self.repetition_limit = repetition_limit
        self.repetition_window = repetition_window

        # Environment-specific eligibility rules
        self._eligibility_rules = {
            'prod': ['noop', 'restart'],  # Production frozen mode: noop-first, restart only
            'stage': ['restart', 'noop', 'scale_up', 'scale_down'],  # Stage: safe actions
            'dev': ['restart', 'scale_up', 'noop', 'scale_down', 'rollback']  # Dev: all actions
        }
        
        self._lock = threading.Lock()
        
        # Track last execution time for each action
        self._last_execution: Dict[str, float] = {}
        
        # Track action history (sliding window)
        self._action_history: deque = deque(maxlen=100)

        # Load persisted state
        self._load_state()

        self._policy_engine = DeterministicPolicyEngine(
            policy_id=self.POLICY_ID,
            runtime_policy_version=self.POLICY_VERSION,
            policy_definition=self.get_config(),
        )
        
        # Phase 3: Append-only persistence journal for deterministic replay
        self._append_only_log = AppendOnlyLog(
            log_path="logs/control_plane/append_only_log.jsonl"
        )
    
    def _load_state(self):
        state_path = "logs/control_plane/governance_state.json"
        with self._lock:
            self._last_execution = {}
            self._action_history = deque(maxlen=100)
            if os.path.exists(state_path):
                try:
                    with open(state_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._last_execution = data.get("last_execution", {})
                        history_data = data.get("action_history", [])
                        for record in history_data:
                            self._action_history.append(
                                ActionRecord(
                                    action=record["action"],
                                    timestamp=record["timestamp"],
                                    context=record.get("context", {})
                                )
                            )
                except Exception:
                    pass

    def _save_state(self):
        state_path = "logs/control_plane/governance_state.json"
        with self._lock:
            try:
                os.makedirs(os.path.dirname(state_path), exist_ok=True)
                history_data = [
                    {
                        "action": record.action,
                        "timestamp": record.timestamp,
                        "context": record.context
                    }
                    for record in self._action_history
                ]
                with open(state_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "last_execution": self._last_execution,
                        "action_history": history_data
                    }, f)
            except Exception:
                pass

    def evaluate_action(
        self,
        action: str,
        context: Dict[str, Any],
        source: Optional[str] = None
    ) -> GovernanceDecision:
        """Evaluate whether action should be allowed.
        
        Checks in priority order:
        1. Action eligibility
        2. Cooldown enforcement
        3. Repetition suppression
        
        Args:
            action: Action name to evaluate
            context: Action context
            source: Source identifier
            
        Returns:
            GovernanceDecision indicating allow/block
        """
        current_time = time.time()

        # 1. Eligibility Check
        eligibility_check = self._check_eligibility(action, context)
        if eligibility_check.should_block:
            return eligibility_check

        # 2. Cooldown Check
        cooldown_check = self._check_cooldown(action, current_time)
        if cooldown_check.should_block:
            return cooldown_check

        # 3. Repetition Suppression Check
        repetition_check = self._check_repetition(action, current_time)
        if repetition_check.should_block:
            return repetition_check

        policy_def = self.get_config()
        policy_hash = compute_policy_hash(policy_def)
        policy_snapshot = PolicySnapshot(
            policy_id=self.POLICY_ID,
            policy_version=self.POLICY_VERSION,
            policy_hash=policy_hash,
        )

        decision = self._policy_engine.admit(
            PolicyAdmissionRequest(
                action=action,
                context={**context, "source": source or context.get("source", "legacy"), "env": self.env},
                policy_version=self.POLICY_VERSION,
                runtime_policy_version=self.POLICY_VERSION,
                governance_contract=self.build_governance_contract(context=context),
                decision_contract=validate_decision_contract({
                    'decision_type': 'execution',
                    'action': action,
                    'parameters': {
                        'app_name': context.get('app_name'),
                        'source': source or 'legacy',
                    },
                    'version': self.POLICY_VERSION,
                }),
            )
        )

        if decision.allowed:
            self._record_action(action, current_time, context)
            return GovernanceDecision(
                should_block=False,
                policy_id=self.POLICY_ID,
                policy_version=self.POLICY_VERSION,
                policy_hash=policy_hash,
                admission_state=decision.state.value,
                legitimacy=decision.legitimacy,
            )

        return GovernanceDecision(
            should_block=True,
            reason=decision.reason,
            details=decision.details,
            policy_id=self.POLICY_ID,
            policy_version=self.POLICY_VERSION,
            policy_hash=policy_hash,
            admission_state=decision.state.value,
            rejection_code=decision.rejection_code.value if decision.rejection_code else None,
            legitimacy=decision.legitimacy,
        )

    def evaluate_contract(
        self,
        decision: DecisionContract | dict,
        context: Dict[str, Any],
        source: Optional[str] = None,
    ) -> GovernanceDecision:
        if not isinstance(decision, DecisionContract):
            decision = validate_decision_contract(decision)

        current_time = time.time()

        # 1. Eligibility Check
        eligibility_check = self._check_eligibility(decision.action, context)
        if eligibility_check.should_block:
            eligibility_check.legitimacy = "LEGITIMATE_VALID"
            return eligibility_check

        # 2. Cooldown Check
        cooldown_check = self._check_cooldown(decision.action, current_time)
        if cooldown_check.should_block:
            cooldown_check.legitimacy = "LEGITIMATE_VALID"
            return cooldown_check

        # 3. Repetition Suppression Check
        repetition_check = self._check_repetition(decision.action, current_time)
        if repetition_check.should_block:
            repetition_check.legitimacy = "LEGITIMATE_VALID"
            return repetition_check

        policy_hash = compute_policy_hash(self.get_config())
        admission = self._policy_engine.admit(
            PolicyAdmissionRequest(
                action=decision.action,
                context={
                    **context,
                    "decision_type": decision.decision_type,
                    "decision_version": decision.version,
                    "decision_parameters": decision.parameters,
                    "source": source or context.get("source", "legacy"),
                    "env": context.get("env", self.env),
                },
                policy_version=decision.version,
                runtime_policy_version=self.POLICY_VERSION,
                governance_contract=self.build_governance_contract(context=context),
                decision_contract=decision,
                execution_contract=context.get("execution_contract"),
                policy_id=self.POLICY_ID,
            )
        )

        if admission.allowed:
            self._record_action(decision.action, time.time(), context)
            return GovernanceDecision(
                should_block=False,
                policy_id=self.POLICY_ID,
                policy_version=self.POLICY_VERSION,
                policy_hash=policy_hash,
                admission_state=admission.state.value,
                legitimacy=admission.legitimacy,
            )

        return GovernanceDecision(
            should_block=True,
            reason=admission.reason,
            details=admission.details,
            policy_id=self.POLICY_ID,
            policy_version=self.POLICY_VERSION,
            policy_hash=policy_hash,
            admission_state=admission.state.value,
            rejection_code=admission.rejection_code.value if admission.rejection_code else None,
            legitimacy=admission.legitimacy,
        )

    def build_governance_contract(
        self,
        context: Dict[str, Any],
        governance_approver: str = "sarathi",
    ):
        return self._policy_engine.build_governance_contract(
            governance_approver=governance_approver,
            constraints=self.get_config(),
        )

    def get_policy_engine(self) -> DeterministicPolicyEngine:
        return self._policy_engine
    
    def _check_eligibility(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> GovernanceDecision:
        """Check if action is eligible for execution.
        
        Args:
            action: Action name
            context: Action context
            
        Returns:
            GovernanceDecision
        """
        allowed_actions = self._eligibility_rules.get(self.env, ['noop'])
        
        if action not in allowed_actions:
            return GovernanceDecision(
                should_block=True,
                reason=GovernanceReason.ACTION_NOT_ELIGIBLE.value,
                policy_id=self.POLICY_ID,
                admission_state=AdmissionState.EXECUTION_DENIED.value,
                rejection_code=RejectionCode.EXECUTION_NOT_PERMITTED.value,
                details={
                    'action': action,
                    'env': self.env,
                    'allowed_actions': allowed_actions,
                    'message': f'Action {action} not eligible in {self.env} environment'
                }
            )
        
        # Check prerequisites (e.g., app must exist to be restarted)
        prerequisite_check = self._check_prerequisites(action, context)
        if prerequisite_check.should_block:
            return prerequisite_check
        
        return GovernanceDecision(should_block=False)
    
    def _check_prerequisites(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> GovernanceDecision:
        """Check action-specific prerequisites.
        
        Args:
            action: Action name
            context: Action context
            
        Returns:
            GovernanceDecision
        """
        # For restart/scale actions, app should exist
        if action in ['restart', 'scale_up', 'scale_down']:
            app_name = context.get('app_name')
            if not app_name:
                return GovernanceDecision(
                    should_block=True,
                    reason=GovernanceReason.PREREQUISITE_NOT_MET.value,
                    policy_id=self.POLICY_ID,
                    admission_state=AdmissionState.EXECUTION_DENIED.value,
                    rejection_code=RejectionCode.EXECUTION_NOT_PERMITTED.value,
                    details={
                        'action': action,
                        'missing_prerequisite': 'app_name',
                        'message': f'Action {action} requires app_name in context'
                    }
                )
        
        # For rollback, previous version should exist
        if action == 'rollback':
            has_previous = context.get('has_previous_version', True)
            if not has_previous:
                return GovernanceDecision(
                    should_block=True,
                    reason=GovernanceReason.PREREQUISITE_NOT_MET.value,
                    policy_id=self.POLICY_ID,
                    admission_state=AdmissionState.EXECUTION_DENIED.value,
                    rejection_code=RejectionCode.EXECUTION_NOT_PERMITTED.value,
                    details={
                        'action': action,
                        'missing_prerequisite': 'previous_version',
                        'message': 'Cannot rollback without previous version'
                    }
                )
        
        return GovernanceDecision(should_block=False)
    
    def _check_cooldown(
        self,
        action: str,
        current_time: float
    ) -> GovernanceDecision:
        """Check if action is on cooldown.
        
        Args:
            action: Action name
            current_time: Current timestamp
            
        Returns:
            GovernanceDecision
        """
        self._load_state()
        cooldown_period = self.cooldown_periods.get(action, 0)
        
        if cooldown_period == 0:
            return GovernanceDecision(should_block=False)
        
        last_execution = self._last_execution.get(action)
        
        if last_execution:
            time_since_last = current_time - last_execution
            if time_since_last < cooldown_period:
                time_remaining = cooldown_period - time_since_last
                return GovernanceDecision(
                    should_block=True,
                    reason=GovernanceReason.COOLDOWN_ACTIVE.value,
                    policy_id=self.POLICY_ID,
                    admission_state=AdmissionState.POLICY_REJECTED.value,
                    rejection_code=RejectionCode.GOVERNANCE_REJECTED.value,
                    details={
                        'action': action,
                        'last_execution': last_execution,
                        'cooldown_period': f'{cooldown_period}s',
                        'time_since_last': f'{time_since_last:.1f}s',
                        'time_remaining': f'{time_remaining:.1f}s',
                        'message': f'Action {action} on cooldown for {time_remaining:.1f}s'
                    }
                )
        
        return GovernanceDecision(should_block=False)
    
    def _check_repetition(
        self,
        action: str,
        current_time: float
    ) -> GovernanceDecision:
        """Check if action is being repeated too frequently.
        
        Args:
            action: Action name
            current_time: Current timestamp
            
        Returns:
            GovernanceDecision
        """
        self._load_state()
        if action in ["noop", "abstain"]:
            return GovernanceDecision(should_block=False)
            
        # Get recent actions within the repetition window
        cutoff_time = current_time - self.repetition_window
        recent_actions = [
            record for record in self._action_history
            if record.timestamp > cutoff_time and record.action == action
        ]
        
        if len(recent_actions) >= self.repetition_limit:
            return GovernanceDecision(
                should_block=True,
                reason=GovernanceReason.REPETITION_LIMIT_EXCEEDED.value,
                policy_id=self.POLICY_ID,
                admission_state=AdmissionState.POLICY_REJECTED.value,
                rejection_code=RejectionCode.GOVERNANCE_REJECTED.value,
                details={
                    'action': action,
                    'action_history': [r.action for r in recent_actions],
                    'window': f'{self.repetition_window}s',
                    'limit': self.repetition_limit,
                    'actual': len(recent_actions),
                    'message': f'Action {action} repeated {len(recent_actions)} times in {self.repetition_window}s (limit: {self.repetition_limit})'
                }
            )
        
        return GovernanceDecision(should_block=False)
    
    def _record_action(
        self,
        action: str,
        timestamp: float,
        context: Dict[str, Any]
    ):
        """Record action execution.
        
        Args:
            action: Action name
            timestamp: Execution timestamp
            context: Action context
        """
        # Update last execution time
        self._last_execution[action] = timestamp
        
        # Add to history
        record = ActionRecord(
            action=action,
            timestamp=timestamp,
            context=context
        )
        self._action_history.append(record)
        
        # Phase 3: Append to deterministic persistence journal
        import uuid
        from control_plane.persistence.hash_lineage_verifier import HashLineageVerifier
        
        execution_id = context.get('execution_id', str(uuid.uuid4()))
        event_id = str(uuid.uuid4())
        
        details = {
            'action': action,
            'context_keys': list(context.keys()),
            'app_name': context.get('app_name'),
            'env': context.get('env')
        }
        
        # Build canonical payload to compute event_hash
        event_payload = {
            'execution_id': execution_id,
            'event_id': event_id,
            'state': "ACTION_RECORDED",
            'timestamp': int(timestamp),
            'source': "action_governance",
            'details': details
        }
        
        event_hash = HashLineageVerifier._compute_event_hash(event_payload)
        
        try:
            self._append_only_log.append(
                execution_id=execution_id,
                event_id=event_id,
                state=event_payload['state'],
                timestamp=event_payload['timestamp'],
                event_hash=event_hash,
                previous_hash=self._append_only_log._execution_last_hashes.get(execution_id, ""),
                source=event_payload['source'],
                details=details
            )
        except Exception:
            # Persistence errors should not block governance
            pass
        
        self._save_state()
    
    def get_action_history(
        self,
        action: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent action history.
        
        Args:
            action: Filter by action name (None for all)
            limit: Max number of records
            
        Returns:
            List of action records
        """
        history = list(self._action_history)
        
        if action:
            history = [r for r in history if r.action == action]
        
        # Return most recent first
        history.reverse()
        history = history[:limit]
        
        return [
            {
                'action': r.action,
                'timestamp': r.timestamp,
                'context': r.context
            }
            for r in history
        ]
    
    def reset(self):
        """Reset governance state (useful for testing)."""
        self._last_execution.clear()
        self._action_history.clear()
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration.
        
        Returns:
            Configuration dictionary
        """
        return {
            'env': self.env,
            'cooldown_periods': self.cooldown_periods,
            'repetition_limit': self.repetition_limit,
            'repetition_window': self.repetition_window,
            'eligibility_rules': self._eligibility_rules.get(self.env, [])
        }


def get_governance(env: str = 'dev') -> ActionGovernance:
    """Get action governance instance.
    
    Args:
        env: Environment name
        
    Returns:
        ActionGovernance instance
    """
    return ActionGovernance(env=env)
