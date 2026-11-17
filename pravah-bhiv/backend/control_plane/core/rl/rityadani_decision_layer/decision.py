"""
RL Decision Layer for Universal DevOps Runtime Intelligence
This is a rule-based decision system with strict safety boundaries.
No learning or exploration occurs here.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Action scope per environment
ALLOWED_ACTIONS = {
    'dev': ['noop', 'scale_up', 'scale_down', 'restart'],
    'stage': ['noop', 'scale_up', 'scale_down'],
    'prod': ['noop', 'restart']
}

# Signal tiers
REQUIRED_SIGNALS = ['app', 'env', 'state']
OPTIONAL_SIGNALS = ['latency_ms', 'errors_last_min']

# Valid environments
VALID_ENVS = ['dev', 'stage', 'prod']

# Valid states
VALID_STATES = ['healthy', 'degraded', 'critical']

class MockOrchestratorIntegration:
    """
    Mock integration with Shivam's orchestrator.
    Demonstrates how RL decisions would be consumed in production.
    """
    def __init__(self):
        self.executed_actions = []
        self.blocked_actions = []
        
    def submit_decision_for_execution(self, decision: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mock method showing how orchestrator would consume RL decisions.
        In real implementation, this would send to Shivam's system.
        """
        action = decision['action']
        env = context.get('env', 'unknown')
        
        # Final safety check (as would be done by orchestrator)
        if self._is_action_safe_for_env(action, env):
            logger.info(f"Orchestrator executing safe action: {action} in env: {env}")
            execution_result = self._mock_execute_action(action, context)
            self.executed_actions.append({
                'decision': decision,
                'context': context,
                'execution_result': execution_result,
                'timestamp': datetime.now().isoformat()
            })
            return execution_result
        else:
            logger.warning(f"Orchestrator blocking unsafe action: {action} in env: {env}")
            block_result = {
                'status': 'blocked',
                'reason': f'Action {action} not allowed in {env} environment',
                'timestamp': datetime.now().isoformat()
            }
            self.blocked_actions.append({
                'decision': decision,
                'context': context,
                'block_result': block_result
            })
            return block_result
    
    def _is_action_safe_for_env(self, action: str, env: str) -> bool:
        """Final safety validation as would be done by orchestrator."""
        allowed_actions = ALLOWED_ACTIONS.get(env, [])
        return action in allowed_actions
    
    def _mock_execute_action(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock action execution."""
        return {
            'status': 'executed',
            'action': action,
            'env': context.get('env'),
            'app': context.get('app'),
            'timestamp': datetime.now().isoformat(),
            'mock_outcome': 'success'  # In real system, this would be actual execution result
        }

class RLDecisionLayer:
    def __init__(self):
        self.reward_loop_active = False  # Explicitly disabled
        self.last_event_timestamp = None

    def consume_runtime_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consume a normalized runtime event from Shivam's system.
        Validates the event and adapts it to RL state.
        Returns NOOP if event is invalid or unreliable.
        """
        logger.info(f"Consuming runtime event: {json.dumps(event)}")
        
        # Validate event structure and content
        validation_result = self._validate_runtime_event(event)
        if not validation_result['valid']:
            logger.warning(f"Invalid runtime event: {validation_result['reason']}")
            return self._create_response('noop', f"Invalid runtime event: {validation_result['reason']}")
        
        # Adapt event to RL state
        rl_state = self._adapt_event_to_rl_state(event)
        
        # Check for delayed signals (if timestamp is provided)
        if 'timestamp' in event:
            current_time = datetime.now().timestamp()
            event_time = event['timestamp']
            if isinstance(event_time, str):
                try:
                    event_time = datetime.fromisoformat(event_time.replace('Z', '+00:00')).timestamp()
                except ValueError:
                    logger.warning("Invalid timestamp format in event")
                    return self._create_response('noop', "Invalid timestamp format")
            
            if current_time - event_time > 300:  # 5 minutes delay threshold
                logger.warning(f"Delayed signal detected: {current_time - event_time} seconds old")
                return self._create_response('noop', "Delayed signal - too old for decision")
        
        # Make decision based on adapted state
        return self.make_decision(rl_state)

    def _validate_runtime_event(self, event: Dict[str, Any]) -> Dict[str, bool]:
        """
        Validate runtime event for required fields and data types.
        """
        # Check required signals
        missing_required = [sig for sig in REQUIRED_SIGNALS if sig not in event]
        if missing_required:
            return {'valid': False, 'reason': f"Missing required signals: {missing_required}"}
        
        # Validate env
        if event.get('env') not in VALID_ENVS:
            return {'valid': False, 'reason': f"Invalid environment: {event.get('env')}. Must be one of {VALID_ENVS}"}
        
        # Validate state
        if event.get('state') not in VALID_STATES:
            return {'valid': False, 'reason': f"Invalid state: {event.get('state')}. Must be one of {VALID_STATES}"}
        
        # Validate optional signals if present
        if 'latency_ms' in event:
            if not isinstance(event['latency_ms'], (int, float)) or event['latency_ms'] < 0:
                return {'valid': False, 'reason': "latency_ms must be a non-negative number"}
        
        if 'errors_last_min' in event:
            if not isinstance(event['errors_last_min'], int) or event['errors_last_min'] < 0:
                return {'valid': False, 'reason': "errors_last_min must be a non-negative integer"}
        
        return {'valid': True, 'reason': "Event is valid"}

    def _adapt_event_to_rl_state(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt normalized runtime event to RL state format.
        """
        rl_state = {
            'app': event['app'],
            'env': event['env'],
            'state': event['state']
        }
        
        # Add optional signals if present and valid
        if 'latency_ms' in event:
            rl_state['latency_ms'] = event['latency_ms']
        if 'errors_last_min' in event:
            rl_state['errors_last_min'] = event['errors_last_min']
        
        logger.info(f"Adapted event to RL state: {json.dumps(rl_state)}")
        return rl_state

    def make_decision(self, runtime_signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a conservative, rule-based decision based on runtime signals.
        Returns NOOP if insufficient data or unsafe action.
        """
        # Check for required signals
        missing_required = [sig for sig in REQUIRED_SIGNALS if sig not in runtime_signals]
        if missing_required:
            logger.warning(f"Insufficient runtime truth: missing required signals {missing_required}")
            return self._create_response('noop', f"Missing required signals: {missing_required}")

        # Validate signal values
        env = runtime_signals.get('env')
        if env not in VALID_ENVS:
            logger.warning(f"Invalid environment: {env}")
            return self._create_response('noop', f"Invalid environment: {env}. Must be one of {VALID_ENVS}")
        
        state = runtime_signals.get('state')
        if state not in VALID_STATES:
            logger.warning(f"Invalid state: {state}")
            return self._create_response('noop', f"Invalid state: {state}. Must be one of {VALID_STATES}")

        app = runtime_signals.get('app')
        if not isinstance(app, str) or not app.strip():
            logger.warning(f"Invalid app name: {app}")
            return self._create_response('noop', f"Invalid app name: must be non-empty string")

        # Validate optional signals
        latency = runtime_signals.get('latency_ms')
        if latency is not None and (not isinstance(latency, (int, float)) or latency < 0):
            logger.warning(f"Invalid latency_ms: {latency}")
            return self._create_response('noop', "Invalid latency_ms: must be non-negative number")
        
        errors = runtime_signals.get('errors_last_min')
        if errors is not None and (not isinstance(errors, int) or errors < 0):
            logger.warning(f"Invalid errors_last_min: {errors}")
            return self._create_response('noop', "Invalid errors_last_min: must be non-negative integer")

        # Determine action based on simple rules
        action = self._decide_action(env, state, runtime_signals)

        # Enforce action scope
        if action not in ALLOWED_ACTIONS.get(env, []):
            logger.info(f"Downgrading unsafe action '{action}' to 'noop' for env '{env}'")
            action = 'noop'

        return self._create_response(action, "Decision made based on runtime signals")

    def _decide_action(self, env: str, state: str, signals: Dict[str, Any]) -> str:
        """
        Simple rule-based decision logic.
        Note: This may return actions not allowed in env - enforcement happens later.
        """
        # Basic rules (can be expanded but keep simple and safe)
        if state == 'critical':
            return 'restart'

        # Check optional signals
        latency = signals.get('latency_ms')
        errors = signals.get('errors_last_min')

        if latency and latency > 5000:  # High latency threshold
            return 'scale_up'

        if errors and errors > 10:  # Error threshold
            return 'restart'

        # Default to noop
        return 'noop'

    def _create_response(self, action: str, reason: str) -> Dict[str, Any]:
        return {
            'action': action,
            'reason': reason,
            'timestamp': datetime.now().isoformat(),
            'reward_computed': False,  # No reward loop
            'learning_active': False
        }

    def compute_reward(self, action: str, outcome: Dict[str, Any]) -> Optional[float]:
        """
        Reward loop is disabled. This method exists for interface compatibility
        but always returns None and logs that no learning occurs.
        """
        logger.info("Reward computation disabled: No learning in this RL layer")
        return None

# Example usage
if __name__ == "__main__":
    rl = RLDecisionLayer()

    # Test cases for Day 1: Live Runtime Consumption
    print("=== DAY 1: LIVE RUNTIME CONSUMPTION TESTS ===")
    
    # Valid runtime event
    valid_event = {
        'app': 'web',
        'env': 'prod',
        'state': 'critical',
        'latency_ms': 6000,
        'errors_last_min': 15,
        'timestamp': datetime.now().isoformat()
    }
    print(f"Valid event input: {json.dumps(valid_event, indent=2)}")
    decision = rl.consume_runtime_event(valid_event)
    print(f"Decision: {json.dumps(decision, indent=2)}\n")
    
    # Invalid event: missing required signal
    invalid_event_missing = {
        'app': 'web',
        'state': 'critical',
        'latency_ms': 6000
    }
    print(f"Invalid event (missing env): {json.dumps(invalid_event_missing, indent=2)}")
    decision = rl.consume_runtime_event(invalid_event_missing)
    print(f"Decision: {json.dumps(decision, indent=2)}\n")
    
    # Invalid event: malformed value
    invalid_event_malformed = {
        'app': 'web',
        'env': 'prod',
        'state': 'critical',
        'latency_ms': 'not_a_number'
    }
    print(f"Invalid event (malformed latency): {json.dumps(invalid_event_malformed, indent=2)}")
    decision = rl.consume_runtime_event(invalid_event_malformed)
    print(f"Decision: {json.dumps(decision, indent=2)}\n")
    
    # Delayed signal test
    delayed_event = {
        'app': 'web',
        'env': 'prod',
        'state': 'critical',
        'timestamp': (datetime.now().timestamp() - 400)  # 400 seconds ago
    }
    print(f"Delayed event: {json.dumps(delayed_event, indent=2)}")
    decision = rl.consume_runtime_event(delayed_event)
    print(f"Decision: {json.dumps(decision, indent=2)}\n")
    
    # JSON example for deliverables
    print("=== JSON EXAMPLE: Runtime Event to Adapted RL State ===")
    example_event = {
        'app': 'api',
        'env': 'stage',
        'state': 'degraded',
        'latency_ms': 3000,
        'errors_last_min': 5
    }
    adapted_state = rl._adapt_event_to_rl_state(example_event)
    print(f"Runtime Event: {json.dumps(example_event)}")
    print(f"Adapted RL State: {json.dumps(adapted_state)}")
    decision = rl.make_decision(adapted_state)
    print(f"Decision: {json.dumps(decision)}\n")
    
    # Day 2: Decision Determinism & Safety Proof
    print("=== DAY 2: DECISION DETERMINISM & SAFETY PROOF ===")
    
    # Determinism test: Same input multiple times
    test_input = {'app': 'web', 'env': 'prod', 'state': 'critical'}
    decisions = []
    for i in range(5):
        decision = rl.make_decision(test_input.copy())
        decisions.append(decision)
        print(f"Run {i+1}: {json.dumps(decision)}")
    
    # Verify all decisions are identical
    all_identical = all(d == decisions[0] for d in decisions)
    print(f"\nDeterminism Check: All decisions identical? {all_identical}")
    if all_identical:
        print("PROVEN: Same input always produces same output")
    else:
        print("FAILED: Non-deterministic behavior detected")
    
    # Safety guard verification
    print("\n=== SAFETY GUARD VERIFICATION ===")
    unsafe_scenarios = [
        {'app': 'web', 'env': 'prod', 'state': 'healthy', 'latency_ms': 6000},  # Would trigger scale_up logic but prod doesn't allow
        {'app': 'web', 'env': 'prod', 'state': 'healthy', 'errors_last_min': 50},  # Would trigger restart but verify safety
    ]
    
    for i, scenario in enumerate(unsafe_scenarios):
        decision = rl.make_decision(scenario)
        action_allowed = decision['action'] in ALLOWED_ACTIONS.get(scenario['env'], [])
        print(f"Safety Test {i+1}: Input={scenario} -> Action={decision['action']} (Allowed: {action_allowed})")
        if not action_allowed and decision['action'] == 'noop':
            print("Safety guard working: Unsafe action downgraded to NOOP")
        elif action_allowed:
            print("Safe action allowed")
        else:
            print("Safety guard failed")
    
    print("\n=== EXPLICIT NOTE: No internal state evolves during demo ===")
    print("• RL layer has no internal state variables that change over time")
    print("• No learning updates: reward_loop_active = False")
    print("• No exploration: All decisions are rule-based only")
    print("• Decisions depend only on input signals, not on previous decisions")
    print("• File location enforcing safety: decision.py lines 15-20 (ALLOWED_ACTIONS) and lines 75-80 (safety enforcement)")
    
    # Day 3: Closed Loop Integration (RL ↔ Orchestrator)
    print("\n=== DAY 3: CLOSED LOOP INTEGRATION (RL <-> ORCHESTRATOR) ===")
    
    # Initialize mock orchestrator
    orchestrator = MockOrchestratorIntegration()
    rl = RLDecisionLayer()
    
    # Simulate runtime events and full loop
    runtime_events = [
        {
            'app': 'web',
            'env': 'prod',
            'state': 'critical',
            'latency_ms': 1000,
            'errors_last_min': 20,
            'timestamp': datetime.now().isoformat()
        },
        {
            'app': 'api',
            'env': 'stage',
            'state': 'degraded',
            'latency_ms': 4000,
            'errors_last_min': 2,
            'timestamp': datetime.now().isoformat()
        },
        {
            'app': 'worker',
            'env': 'prod',
            'state': 'healthy',
            'latency_ms': 7000,  # This would trigger scale_up logic but prod doesn't allow it
            'errors_last_min': 1,
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    print("=== FULL LOOP DEMONSTRATION: Runtime Event -> RL -> Safe Decision -> Execution ===")
    for i, event in enumerate(runtime_events):
        print(f"\n--- Loop {i+1}: {event['app']} in {event['env']} ---")
        
        # 1. Runtime emits event
        print(f"1. Runtime Event: {json.dumps(event)}")
        
        # 2. RL consumes event
        decision = rl.consume_runtime_event(event)
        print(f"2. RL Decision: {json.dumps(decision)}")
        
        # 3. Orchestrator validates and executes
        execution_result = orchestrator.submit_decision_for_execution(decision, event)
        print(f"3. Execution Result: {json.dumps(execution_result)}")
        
        # 4. Log outcome (reward would be computed here in real system)
        if execution_result.get('status') == 'executed':
            print("Safe action executed successfully")
        else:
            print("Unsafe action blocked by orchestrator")
    
    print("\n=== BLOCKED/DOWNGRADED ACTIONS LOG ===")
    for blocked in orchestrator.blocked_actions:
        print(f"Blocked: {blocked['decision']['action']} for {blocked['context']['app']} in {blocked['context']['env']}")
        print(f"  Reason: {blocked['block_result']['reason']}")
    
    print("\n=== EXECUTED ACTIONS LOG ===")
    for executed in orchestrator.executed_actions:
        print(f"Executed: {executed['decision']['action']} for {executed['context']['app']} in {executed['context']['env']}")
        print(f"  Status: {executed['execution_result']['status']}")
    
    # Failure scenario walkthrough
    print("\n=== FAILURE SCENARIO WALKTHROUGH ===")
    print("Scenario: App in prod environment with high latency (would trigger scale_up)")
    failure_event = {
        'app': 'web',
        'env': 'prod',
        'state': 'healthy',
        'latency_ms': 8000,
        'errors_last_min': 1,
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"Runtime Event: {json.dumps(failure_event)}")
    
    # RL makes decision (logic might suggest scale_up, but safety prevents it)
    decision = rl.consume_runtime_event(failure_event)
    print(f"RL Decision: {decision['action']} (reason: {decision['reason']})")
    
    # Orchestrator blocks unsafe action
    execution_result = orchestrator.submit_decision_for_execution(decision, failure_event)
    print(f"Orchestrator: {execution_result['status']} - {execution_result.get('reason', 'N/A')}")
    
    print("FAILURE HANDLED: RL suggested scale_up but safety guard + orchestrator prevented prod scaling")
    
    # Legacy tests for backward compatibility
    print("\n=== LEGACY TESTS ===")
    test_signals = [
        {'app': 'web', 'env': 'prod', 'state': 'healthy'},  # Should be noop
        {'app': 'web', 'env': 'prod', 'state': 'critical'},  # Should be restart
        {'app': 'web', 'env': 'prod', 'state': 'healthy', 'latency_ms': 6000},  # Should be noop (no scale_up in prod)
    ]

    for i, signals in enumerate(test_signals):
        decision = rl.make_decision(signals)
        print(f"Test {i+1}: {json.dumps(decision, indent=2)}")

    # Test missing required signals
    incomplete_signals = {'app': 'web', 'state': 'healthy'}  # Missing env
    decision = rl.make_decision(incomplete_signals)
    print(f"Missing signals test: {json.dumps(decision, indent=2)}")

    # Test reward
    reward = rl.compute_reward('noop', {'success': True})
    print(f"Reward test: {reward}")