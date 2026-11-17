"""
Proof Logger - Captures timestamped events for demo verification
"""

import json
import datetime
import os
from typing import Dict, Any
from enum import Enum

class ProofEvents(Enum):
    """Enumeration of proof event types"""
    RUNTIME_EMIT = "RUNTIME_EMIT"
    RL_CONSUME = "RL_CONSUME"
    RL_DECISION = "RL_DECISION"
    ORCH_EXEC = "ORCH_EXEC"
    ORCH_REFUSE = "ORCH_REFUSE"
    SYSTEM_STABLE = "SYSTEM_STABLE"
    FAILURE_INJECTED = "FAILURE_INJECTED"
    REFUSAL_EMIT_SUCCESS = "REFUSAL_EMIT_SUCCESS"
    # Demo Mode Execution Gate Events
    DEMO_MODE_BLOCK = "DEMO_MODE_BLOCK"
    EXECUTION_GATE_PASSED = "EXECUTION_GATE_PASSED"
    UNSAFE_ACTION_REFUSED = "UNSAFE_ACTION_REFUSED"
    RL_INTAKE_VALIDATED = "RL_INTAKE_VALIDATED"
    RL_INPUT = "RL_INPUT"
    # Onboarding Events
    ONBOARDING_STARTED = "ONBOARDING_STARTED"
    ONBOARDING_VALIDATION_PASSED = "ONBOARDING_VALIDATION_PASSED"
    ONBOARDING_REJECTED = "ONBOARDING_REJECTED"
    SPEC_GENERATED = "SPEC_GENERATED"
    DEPLOYMENT_TRIGGERED = "DEPLOYMENT_TRIGGERED"
    # Action Governance Events (Day 2)
    GOVERNANCE_BLOCK = "GOVERNANCE_BLOCK"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    REPETITION_SUPPRESSED = "REPETITION_SUPPRESSED"
    ACTION_ELIGIBILITY_FAILED = "ACTION_ELIGIBILITY_FAILED"
    UNCERTAINTY_NOOP = "UNCERTAINTY_NOOP"
    SIGNAL_CONFLICT_OBSERVE = "SIGNAL_CONFLICT_OBSERVE"

def write_proof(event_name: ProofEvents, data: Dict[str, Any]):
    """Write proof entry to day1 proof log"""
    proof_log = "logs/day1_proof.log"
    os.makedirs(os.path.dirname(proof_log), exist_ok=True)
    
    proof_entry = {
        'event_name': event_name.value,
        'timestamp': datetime.datetime.now().isoformat(),
        **data
    }
    
    with open(proof_log, 'a') as f:
        f.write(json.dumps(proof_entry) + '\n')

class ProofLogger:
    def __init__(self, log_file: str):
        self.log_file = log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Initialize log file with header
        if not os.path.exists(log_file):
            with open(log_file, 'w') as f:
                header = {
                    'log_initialized': datetime.datetime.now().isoformat(),
                    'log_type': 'day2_demo_proof',
                    'format': 'jsonl'
                }
                f.write(json.dumps(header) + '\n')
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Log event with timestamp"""
        log_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'event_type': event_type,
            'data': data
        }
        
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def log_step(self, step_number: int, description: str, details: Dict[str, Any] = None):
        """Log demo step"""
        step_data = {
            'step': step_number,
            'description': description,
            'details': details or {}
        }
        self.log_event('DEMO_STEP', step_data)
    
    def log_scenario_start(self, scenario_name: str):
        """Log scenario start"""
        self.log_event('SCENARIO_START', {'scenario': scenario_name})
    
    def log_scenario_end(self, scenario_name: str, success: bool):
        """Log scenario end"""
        self.log_event('SCENARIO_END', {
            'scenario': scenario_name,
            'success': success
        })