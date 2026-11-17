#!/usr/bin/env python3
"""
Agent Runtime - Autonomous AI Agent Core
Main entry point for the multi-agent CI/CD system operating as an autonomous AI agent.

Agent Loop: sense → validate → decide → enforce → act → observe → explain
State Machine: idle → observing → validating → deciding → enforcing → acting → observing_results → explaining → idle
"""

import argparse
import os
import signal
import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent
control_plane_dir = backend_dir / "control_plane"
if str(control_plane_dir) not in sys.path:
    sys.path.append(str(control_plane_dir))
import logging
logger = logging.getLogger("control_plane.decision_provider")
import time
from unittest import result
import uuid
import threading
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
# from coverage import context  # Unused - context is just a dict variable used in methods
import requests
from control_plane.core.agent_state import AgentState, AgentStateManager
# Core agent modules
# from core.agent_state import AgentState, AgentStateManager
from control_plane.core.agent_logger import AgentLogger
from control_plane.core.agent_memory import AgentMemory
from control_plane.core.perception import PerceptionLayer
from control_plane.core.perception_adapters import (
    RuntimeEventAdapter,
    HealthSignalAdapter,
    OnboardingInputAdapter,
    SystemAlertAdapter
)
from control_plane.core.self_restraint import SelfRestraint
# ADD THIS IMPORT AT TOP WITH OTHER CORE MODULES
from control_plane.core.action_governance import ActionGovernance
from control_plane.core.proof_logger import write_proof, ProofEvents


# Existing system modules
from control_plane.core.env_config import EnvironmentConfig
from control_plane.core.rl_orchestrator_safe import get_safe_executor
from control_plane.agents.multi_deploy_agent import MultiDeployAgent
from control_plane.core.redis_event_bus import RedisEventBus
from control_plane.core.event_bus import EventBus
from control_plane.agents.uptime_monitor import UptimeMonitor
from control_plane.core.runtime_event_validator import RuntimeEventValidator


from core_hooks.signal_builder import build_base_signal
from executer.runner import execute
from sarathi.router import build_sarathi_headers
from contracts.decision_contract import validate_decision_contract
from contracts.execution_contract import build_execution_contract


class ConfigurationError(Exception):
    """Raised when critical configuration is missing."""
    pass

class DecisionProvider:
    """Base interface class for Runtime Decision Providers."""
    def decide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("decide must be implemented by subclasses")


class HTTPDecisionProvider(DecisionProvider):
    """Production decision provider calling the external HTTP engine."""
    def __init__(self, endpoint_url: str = None, timeout: float = 2.0):
        if endpoint_url is None:
            main_api = os.getenv("PRAVAH_MAIN_API")
            if not main_api:
                raise ConfigurationError("PRAVAH_MAIN_API is required for production Decision Brain execution.")
            if main_api.endswith("/"):
                main_api = main_api[:-1]
            endpoint_url = f"{main_api}/process-runtime"
        self.endpoint_url = endpoint_url
        self.timeout = timeout

    def decide(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("HTTPDecisionProvider invoking Decision Brain at: %s", self.endpoint_url)
        response = requests.post(
            self.endpoint_url,
            json=payload,
            timeout=self.timeout
        )
        if not response.text:
            raise ValueError("Empty response from external API")
        return response.json()


def call_decision_engine(runtime_payload):
    main_api = os.getenv("PRAVAH_MAIN_API")
    if not main_api:
        raise ConfigurationError("PRAVAH_MAIN_API is required for production Decision Brain execution.")
    if main_api.endswith("/"):
        main_api = main_api[:-1]
    endpoint_url = f"{main_api}/process-runtime"
    logger.info("call_decision_engine invoking Decision Brain at: %s", endpoint_url)
    response = requests.post(
        endpoint_url,
        json=runtime_payload
    )
    return response.json()


class AgentRuntime:
    """Autonomous AI Agent Runtime with explicit sense-validate-decide-enforce-act-observe-explain loop."""

    
    def __init__(self, env: str = 'dev', agent_id: Optional[str] = None, loop_interval: float = 5.0, decision_provider: Optional[DecisionProvider] = None):
        """Initialize agent runtime.
        
        Args:
            env: Environment (dev/stage/prod)
            agent_id: Unique agent identifier (auto-generated if None)
            loop_interval: Loop cycle interval in seconds
            decision_provider: Decision provider class for deciding actions
        """
        self.execution_mode = "external"   # [RUNTIME] CHANGE THIS
        # Normalize environment aliases for internal consistency
        if env in ('staging', 'stage'):
            env = 'stage'
        elif env in ('production', 'prod'):
            env = 'prod'
        elif env in ('development', 'dev'):
            env = 'dev'

        # Initialize production logging first
        if env == 'prod':
            from control_plane.core.prod_logging import configure_production_logging
            configure_production_logging(level='INFO', format_style='text')
        
        self.agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.env = env
        self.loop_interval = loop_interval
        self.decision_provider = decision_provider or HTTPDecisionProvider()

        self.governance = ActionGovernance(env=self.env)
        # Agent identity
        
        
        # Agent metadata
        self.start_time = datetime.utcnow()
        self.version = "1.0.0"
        self.loop_count = 0
        
        # State management (Recover from last state if possible)
        state_file = Path("logs/agent") / f"agent_state_{self.agent_id}.json"
        if state_file.exists():
            try:
                self.state_manager = AgentStateManager.load_from_file(str(state_file), self.agent_id)
            except Exception:
                self.state_manager = AgentStateManager(self.agent_id)
        else:
            self.state_manager = AgentStateManager(self.agent_id)
        
        # Logging
        from control_plane.core.agent_logger import AgentLogger
        self.logger = AgentLogger(self.agent_id)
        
        # Memory (Recover from last snapshot if possible)
        memory_file = Path("logs/agent") / f"memory_snapshot_{self.agent_id}.json"
        self.memory = AgentMemory(
            max_decisions=50,
            max_states_per_app=10,
            agent_id=self.agent_id
        )
        if memory_file.exists():
            try:
                self.memory.from_json(str(memory_file))
            except Exception:
                pass # Start with fresh memory if load fails
        
        # Perception layer
        self.perception_layer = PerceptionLayer(self.agent_id)
        
        # Self-restraint module (intentional self-blocking)
        # self.self_restraint = SelfRestraint(
        #     min_confidence=0.6,
        #     max_instability_score=75,
        #     max_recent_failures=5
        # )
        
        # Environment configuration
        self.env_config = EnvironmentConfig(env)
        
        # System components
        self._initialize_components()
        
        # Execution lock for sync operations
        import threading
        self._loop_lock = threading.Lock()
        
        # Shutdown flag
        self._shutdown_requested = False
        
        # FIX 5: External visibility - track last decision and block reason
        self._last_decision = None
        self._last_block_reason = None
        self._last_block_type = None
        self._last_legitimacy = None
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Log initialization
        self.logger.info(
            f"Agent initialized: id={self.agent_id}, env={env}, version={self.version}",
            agent_state=self.state_manager.current_state.value
        )
        self.logger.log_autonomous_operation(
            "agent_initialization",
            {
                "agent_id": self.agent_id,
                "environment": env,
                "version": self.version,
                "loop_interval": loop_interval
            },
            self.state_manager.current_state.value
        )
    













    # REMOVED: Duplicate handle_external_event - using the proper one below at line 468












    def _initialize_components(self):
        """Initialize system components."""
        self.logger.info("Initializing system components", agent_state=self.state_manager.current_state.value)
        
        self.rl_pipe = None
        
        # Safe Executor
        self.safe_executor = get_safe_executor(self.env)
        
        # Event Bus (try Redis, fallback to local)
        try:
            self.event_bus = RedisEventBus(env=self.env)
            self.logger.info("Redis event bus initialized", agent_state=self.state_manager.current_state.value)
        except Exception as e:
            self.logger.warning(
                f"Redis unavailable, using local event bus: {e}",
                agent_state=self.state_manager.current_state.value
            )
            self.event_bus = EventBus()
        
        # Uptime Monitor
        uptime_log_file = self.env_config.get_log_path("uptime_log.csv")
        self.uptime_monitor = UptimeMonitor(timeline_file=uptime_log_file)
        
        # Event Validator
        self.event_validator = RuntimeEventValidator()
        
        self.auto_scaler = None
        
        # Issue Detector (will be initialized when needed)
        self.issue_detector = None
        
        # Initialize perception adapters
        self._initialize_perception_adapters()
        
        self.logger.info("All components initialized", agent_state=self.state_manager.current_state.value)
    
    def _initialize_perception_adapters(self):
        """Initialize and register perception adapters."""
        # Runtime events from event bus
        runtime_adapter = RuntimeEventAdapter(self.event_bus)
        self.perception_layer.register_adapter(runtime_adapter)
        
        # Health signals from uptime monitor
        health_adapter = HealthSignalAdapter(self.uptime_monitor)
        self.perception_layer.register_adapter(health_adapter)
        
        # Onboarding input
        self.onboarding_adapter = OnboardingInputAdapter()
        self.perception_layer.register_adapter(self.onboarding_adapter)
        
        # System alerts
        self.alert_adapter = SystemAlertAdapter()
        self.perception_layer.register_adapter(self.alert_adapter)
        
        self.logger.info(
            f"Perception adapters initialized: {len(self.perception_layer.perception_adapters)} adapters",
            agent_state=self.state_manager.current_state.value
        )
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        self.logger.info(
            f"Shutdown signal received: {signum}",
            agent_state=self.state_manager.current_state.value
        )
        self._shutdown_requested = True
    
    def run(self):
        """Run the agent loop continuously."""
        self.logger.info(
            f"Agent runtime starting continuous operation",
            agent_state=self.state_manager.current_state.value
        )
        
        self.logger.log_autonomous_operation(
            "continuous_operation_start",
            {
                "proof": "no_manual_triggers_required",
                "loop_interval": self.loop_interval,
                "autonomous": True
            },
            self.state_manager.current_state.value
        )
        
        try:
            while not self._shutdown_requested:
                with self._loop_lock:
                    self._execute_agent_loop()
                    
                    # Return to idle while still holding the lock (Atomic Cycle)
                    if self.state_manager.current_state != AgentState.IDLE:
                        self.state_manager.transition_to(AgentState.IDLE, "loop_complete")
                
                self.loop_count += 1
                
                # Heartbeat
                uptime = (datetime.utcnow() - self.start_time).total_seconds()
                self.logger.log_heartbeat(self.state_manager.current_state.value, uptime)
                
                time.sleep(self.loop_interval)
        
        except Exception as e:
            self.logger.log_error(
                "agent_loop_error",
                str(e),
                self.state_manager.current_state.value,
                {"exception_type": type(e).__name__}
            )
            raise
        
        finally:
            self._shutdown()
    
    def _execute_agent_loop(self, manual_observation: Optional[Dict[str, Any]] = None):
        """Execute one iteration of the agent loop: sense → validate → decide → enforce → act → observe → explain.
        
        Args:
            manual_observation: Optional external event data to bypass sensing.
        """
        print(">>> LOOP ENTERED <<<")
        
        # SENSE (Observing)
        if manual_observation:
            observation = manual_observation
            # Only transition to OBSERVING if we are IDLE (atomicity check)
            if self.state_manager.current_state == AgentState.IDLE:
                self.state_manager.transition_to(AgentState.OBSERVING, "manual_event_received")
        else:
            observation = self._sense()
        
        if observation is None:
            print("[WARN] No observation - skipping")
            return
        
        # VALIDATE
        self.state_manager.transition_to(AgentState.VALIDATING, "agent_validation_step")
        from security.trace_consumption import is_trace_consumed
        
        trace_id = observation.get("trace_id")
        if trace_id and is_trace_consumed(trace_id):
            validation_result = {
                "valid": False,
                "error_message": f"Trace {trace_id} already consumed"
            }
        else:
            validation_result = {
                "valid": True,
                "validated_data": observation
            }
        
        if not validation_result['valid']:
            # Invalid data, log and return to idle
            self.logger.log_observation(
                "validation_failed",
                validation_result,
                self.state_manager.current_state.value
            )
            self._last_decision = {
                "status": "error",
                "message": validation_result.get("error_message", "validation_failed"),
                "decision": {"action_name": "noop", "source": "validation_failure", "confidence": 0.0}
            }
            return
        
        # DECIDE
        decision = self._decide(validation_result['validated_data'])
        

        






            # ENFORCE FIRST
        print("[DECISION] DECISION REACHED:", decision)

        enforcement_result = self._enforce(decision)






        # Removed: Direct execution - must go through _act() phase instead










        if not enforcement_result['allowed']:
            self.logger.log_observation(
                "action_refused",
                enforcement_result,
                self.state_manager.current_state.value
            )
            return




        
        # FIX 4: Skip ACT phase if status is 'observe' (signal conflict)
        safe_action = enforcement_result.get('safe_action', {})
        execution_result = safe_action.get('execution_result', {})
        
        if execution_result.get('status') == 'observe':
            # Observe-only mode: skip acting, just observe
            self.logger.log_autonomous_operation(
                "observe_only_mode",
                {"reason": execution_result.get('reason', 'signal_conflict')},
                self.state_manager.current_state.value
            )
            # Transition directly to OBSERVING_RESULTS, skip ACT
            observation_result = self._observe({'status': 'observe_mode', 'action': safe_action})
            self._explain(safe_action, {'status': 'observe_mode'}, observation_result)
            return
        
        # ACT - Call the dedicated _act method which handles sarathi signal flow
        self.state_manager.transition_to(AgentState.ACTING, "executing_action")
        validated_data = validation_result['validated_data']
        trace_id = validated_data.get("trace_id")
        app_id = validated_data.get("app_id")
        action_result = self._act(enforcement_result['safe_action'], trace_id, app_id)
        







        
        # OBSERVE
        observation_result = self._observe(action_result)
        
        # EXPLAIN
        self._explain(decision, action_result, observation_result)
    
    def handle_external_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Force the agent to process a specific external event synchronously.
        Respects the FSM lifecycle and uses the execution lock.
        """
        with self._loop_lock:
            # Skip if agent is shutting down
            if self._shutdown_requested:
                raise RuntimeError("Agent is shutting down")
                
            # Perform single shot loop
            try:
                self._execute_agent_loop(manual_observation=event_data)
            finally:
                # Always return to IDLE after manual cycle
                if self.state_manager.current_state != AgentState.IDLE:
                    # self.state_manager.transition_to(AgentState.IDLE, "manual_loop_complete")
                    try:
                        self.state_manager.transition_to(AgentState.IDLE, "manual_loop_complete")
                    except ValueError:
                        # Force reset (safe fallback)
                        # self.state_manager.current_state = AgentState.IDLE
                        try:
                            self.state_manager.transition_to(AgentState.IDLE, "manual_loop_complete")
                        except ValueError:
                            self.logger.warning("Force resetting state to IDLE")
                            self.state_manager._current_state = AgentState.IDLE  # 👈 use internal var
            
            # Return the last decision result (stored during _execute_agent_loop via _explain)
            if not self._last_decision:
                return {
                    "status": "error", 
                    "message": "Cycle complete but no decision was explained (partial loop)",
                    "decision": {"action_name": "noop", "source": "fsm_early_exit", "confidence": 0.0}
                }
            return self._last_decision
    
    def _sense(self) -> Optional[Dict[str, Any]]:
        """SENSE: Observe environment for events/changes using perception layer.
        
        Returns:
            Observed data or None if nothing to process
        """
        self.state_manager.transition_to(AgentState.OBSERVING, "sensing_environment")
        self.logger.log_state_transition(
            AgentState.IDLE.value,
            AgentState.OBSERVING.value,
            "sensing_environment"
        )
        
        try:
            # Use perception layer to aggregate all perceptions
            perceptions = self.perception_layer.perceive()
            
            if perceptions:
                # Get highest priority perception
                perception = self.perception_layer.get_highest_priority_perception(perceptions)
                
                self.logger.log_observation(
                    "perception_detected",
                    {
                        "perception_type": perception.type,
                        "priority": perception.priority,
                        "source": perception.source,
                        "data": perception.data
                    },
                    self.state_manager.current_state.value
                )
                
                # RETURN 1: Found a perception event
                return perception.data
            
            # RETURN 2: Nothing detected, Agent remains Idle
            return None

        except Exception as e:
            self.logger.log_error("sense_error", str(e), self.state_manager.current_state.value)
            self.state_manager.transition_to(AgentState.BLOCKED, f"sense_error: {e}")
            return None
    
    def _validate(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """VALIDATE: Validate observed data.
        
        Args:
            observation: Observed data
            
        Returns:
            Validation result with 'valid' flag and 'validated_data'
        """
        self.state_manager.transition_to(AgentState.VALIDATING, "validating_observation")
        self.logger.log_state_transition(
            AgentState.OBSERVING.value,
            AgentState.VALIDATING.value,
            "validating_observation"
        )
        
        try:
            # Use existing validation
            from control_plane.core.runtime_event_validator import validate_and_log_payload
            
            is_valid, validated_data, error_msg = validate_and_log_payload(
                observation,
                "AGENT_SENSE"
            )
            
            result = {
                'valid': is_valid,
                'validated_data': validated_data if is_valid else observation,
                'error_message': error_msg
            }
            
            self.logger.log_observation(
                "validation_result",
                result,
                self.state_manager.current_state.value
            )
            
            return result
        
        except Exception as e:
            self.logger.log_error(
                "validation_error",
                str(e),
                self.state_manager.current_state.value
            )
            return {'valid': False, 'error_message': str(e)}
        



    # def _map_to_runtime_contract(self, data):
    #     return {
    #         "app_id": data.get("app_id", "unknown"),
    #         "current_replicas": data.get("workers", 1),
    #         "desired_replicas": data.get("workers", 1),
    #         "cpu_usage": data.get("cpu", 0) / 100,
    #         "memory_usage": data.get("memory", 0) / 100,
    #         "error_rate": data.get("error_rate", 0.0),
    #         "latency_p99": 100,
    #         "last_deployment_time": time.time(),
    #         "environment": self.env,
    #         "signals": []
    # }
    def _map_to_runtime_contract(self, data):
        return {
            "app_id": data.get("app_id", "unknown"),
            "current_replicas": data.get("workers", 1),
            "desired_replicas": data.get("workers", 1),
            "trace_id": data.get("trace_id"),

            # [OK] FIX THESE
            "cpu_usage": data.get("cpu_percent", 0),
            "memory_usage": data.get("memory_percent", 0),
            "error_rate": data.get("error_rate", 0),

            "latency_p99": 100,
            "last_deployment_time": time.time(),
            "environment": self.env,

            # [OK] ADD SIGNALS (CRITICAL)
            "signals": [
                {
                    "type": data.get("event_type", "unknown"),
                    "severity": "high"
                }
            ]
    }


    def _decide(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:

        self.state_manager.transition_to(AgentState.DECIDING, "making_decision")

        try:
            payload = self._map_to_runtime_contract(validated_data)

            print("DEBUG PAYLOAD:", payload)

            external_decision = self.decision_provider.decide(payload)

            print("DEBUG RESPONSE:", external_decision)

            action_name = external_decision.get("action_requested", "noop")

            action_map = {
                "noop": 0,
                "restart": 1,
                "scale_up": 2,
                "scale_down": 3,
                "rollback": 4
            }

            decision = {
                "rl_action": action_map.get(action_name, 0),
                "action_name": action_name,
                "source": "external_api",
                "confidence": external_decision.get("confidence", 1.0),
                "reason": external_decision.get("reason"),
                "execution_result": {},
                "timestamp": datetime.utcnow().isoformat(),
                "input_data": validated_data
            }
            return decision

        except Exception as e:
            self.logger.error(f"External decision failed: {e}")

            decision = {
                "rl_action": None,
                "action_name": "invalid",
                "source": "external_api_error",
                "confidence": 0.0,
                "reason": "external_api_failed",
                "execution_result": {},
                "timestamp": datetime.utcnow().isoformat(),
                "input_data": validated_data
            }

            return decision


    def _map_rl_action_to_name(self, rl_action: int) -> str:
        return {
            0: "noop",
            1: "restart",
            2: "scale_up",
            3: "scale_down",
            4: "rollback"
        }.get(rl_action, "invalid")

    
    def _enforce(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """ENFORCE: Apply governance and safety checks.
        
        Args:
            decision: Decision from decide phase
            
        Returns:
            Enforcement result with 'allowed' flag and 'safe_action'
        """
        self.state_manager.transition_to(AgentState.ENFORCING, "governance_enforcement")
        self.logger.log_state_transition(
            AgentState.DECIDING.value,
            AgentState.ENFORCING.value,
            "governance_enforcement"
        )
        
        try:
            rl_action = decision.get("rl_action", 0)
            action_name = self._map_rl_action_to_name(rl_action)
            execution = decision.get("execution_result") or {}

            context = {
                "app_name": decision.get("input_data", {}).get("app_id"),
                "confidence": decision.get("confidence", 1.0)  # Use decision confidence
            }

            governance_result = self.governance.evaluate_action(
                action=action_name,
                context=context,
                source="agent_runtime"
            )
            self._last_legitimacy = governance_result.legitimacy

            if governance_result.should_block:
                # FIX 3: Transition agent state to BLOCKED
                self._last_block_reason = governance_result.reason
                self._last_block_type = getattr(governance_result, 'block_type', 'governance')
                self.state_manager.transition_to(AgentState.BLOCKED, self._last_block_reason)
                
                block_payload = governance_result.to_dict()
                
                # DAY 1 FIX: Add cooldown timing for memory visibility
                if hasattr(governance_result, 'next_allowed_time') and governance_result.next_allowed_time:
                    block_payload['cooldown_until'] = governance_result.next_allowed_time.isoformat()

                self.logger.log_autonomous_operation(
                    "governance_block",
                    block_payload,
                    AgentState.BLOCKED.value
                )

                self.memory.remember_decision(
                    decision_type="governance_block",
                    decision_data=block_payload,
                    outcome="blocked",
                    context=context
                )
                
                # Track for external visibility
                self._last_decision = "noop"
                self._last_block_reason = governance_result.reason
                self._last_block_type = "governance"

                return {
                    "allowed": False,
                    "reason": governance_result.reason,
                    "block_type": "governance"
                }

            if execution.get("status") == "refused":
                return {"allowed": False, "reason": execution.get("reason")}

            return {"allowed": True, "safe_action": decision}

        except Exception as e:
            self.logger.log_error(
                "governance_enforcement_error",
                str(e),
                self.state_manager.current_state.value
            )
            return {"allowed": False, "reason": str(e)}

    def _act(self, safe_action: Dict[str, Any], trace_id: str = None, app_id: str = None) -> Dict[str, Any]:
        """ACT: Execute validated safe action through SARATHI→EXECUTER→PRAVAH.
        
        Args:
            safe_action: Safe action from enforce phase
            trace_id: Trace ID for signal propagation
            app_id: Application ID for target service
        Returns:
            Action result with execution_id
        """
        print("[ACT_PHASE] ACT PHASE TRIGGERED")
        
        
        try:
            # CENTRALIZED EXECUTION: Call the Safe Orchestrator
            rl_action_int = safe_action.get('rl_action', 0)
            # input_data = safe_action.get('input_data', {})
            input_data = safe_action.get("input_data", {})
            context = {
                'app_name': input_data.get('app_id', 'unknown'),
                'event_type': input_data.get('event_type', 'manual'),
                'trigger_metrics': input_data.get('metrics', {}),
                'replicas': input_data.get('workers', 1),
                'max_replicas': 5,
                'min_replicas': 1
            }
            
            # Execute through safety gates
            # execution_result = self.safe_executor.validate_and_execute(
            #     action_index=rl_action_int,
            #     context=context,
            #     source='rl_decision_layer' # Mark source for demo_mode gate
            # )

            # Build signal with sarathi source (trace_id must already be present)
            trace_id = input_data.get('trace_id')
            if not trace_id:
                self.logger.error("Missing trace_id in runtime input_data")
                raise ValueError("Missing trace_id")
            service_id = input_data.get('app_id', 'unknown-app')
            action_name = safe_action.get('action_name', 'noop')
            
            signal = build_base_signal(
                trace_id=trace_id,
                service_id=service_id,
                action=action_name
            )
            
            # Add execution context to signal
            signal['context'] = context
            signal['input_data'] = input_data

            execution_contract = build_execution_contract(
                decision_contract=validate_decision_contract({
                    'decision_type': 'execution',
                    'action': action_name,
                    'parameters': {
                        'service_id': service_id,
                        'trace_id': trace_id,
                    },
                    'version': safe_action.get('version', 'v1'),
                }),
                execution_payload=signal,
                approved_by='sarathi',
            )

            signal['execution_id'] = execution_contract.execution_id
            signal['execution_contract'] = execution_contract.model_dump(mode='json')
            
            # Call executer with signed Sarathi service headers (executer will validate identity and inject execution_id)
            try:
                headers = build_sarathi_headers(signal)
                execution_result = execute(signal, headers)
                # execute() emits to pravah_stream and returns the modified signal
                if execution_result:
                    from security.trace_consumption import consume_trace
                    consume_trace(trace_id)
                    execution_result = {
                        'status': 'success',
                        'execution_id': execution_result.get('execution_id'),
                        'source': execution_result.get('source'),
                        'action_executed': action_name,
                        'message': f'Action {action_name} executed via sarathi→executer→pravah'
                    }
                else:
                    execution_result = {
                        'status': 'success',
                        'action_executed': action_name,
                        'message': f'Action {action_name} emitted to Pravah'
                    }
            except Exception as e:
                self.logger.error(f"Signal execution failed: {e}")
                execution_result = {
                    'status': 'failed',
                    'error': str(e),
                    'action_executed': action_name
                }
                






            # Send execution feedback if rl_pipe is available (optional, graceful fallback)
            feedback_result = {'delivery': {'status': 'skipped'}}
            # rl_pipe is typically None in this deployment, so we skip feedback

            
            self.logger.log_action(
                "execute_safe_action",
                {
                    "action": safe_action.get('action_name'),
                    "result": execution_result,
                    "feedback_delivery": feedback_result.get('delivery', {})
                },
                self.state_manager.current_state.value
            )

            self.logger.info(
                f"Execution mode: {self.execution_mode}",
                agent_state=self.state_manager.current_state.value
            )

            # try:
            #     from control_plane.multi_app_control_plane import MultiAppControlPlane
            #     MultiAppControlPlane(env=self.env).append_decision_history({
            #         'env': self.env,
            #         'app_name': context.get('app_name', 'unknown'),
            #         'event_type': context.get('event_type', 'unknown'),
            #         'decision_action': safe_action.get('action_name'),
            #         'decision_source': safe_action.get('source'),
            #         'confidence': safe_action.get('confidence'),
            #         'executed_action': execution_result.get('action_executed'),
            #         'execution_success': execution_result.get('success'),
            #         'status': 'executed' if execution_result.get('success') else 'refused',
            #         'reason': execution_result.get('reason') or execution_result.get('error')
            #     })
            # except Exception:
            #     pass
            
            # return {
            #     'status': 'executed' if execution_result.get('success') else 'refused',
            #     'action': safe_action,
            #     'execution_details': execution_result,
            #     'execution_feedback': feedback_result,
            #     'timestamp': datetime.utcnow().isoformat()
            # }
        




            try:
                from control_plane.multi_app_control_plane import MultiAppControlPlane

                input_data = safe_action.get("input_data", {})

                # Robust success detection
                # is_success = (
                #     execution_result.get("success") is True or
                #     execution_result.get("status") == "success"
                # )

                status = execution_result.get("status")
                message = execution_result.get("message", "")

                # [RUNTIME] FIX LOGIC
                is_success = (
                    status == "success" and "None restarted" not in message
                )
                # Safe executed action fallback
                executed_action = (
                    execution_result.get("action_executed")
                    or safe_action.get("action_name")
                )

                MultiAppControlPlane(env=self.env).append_decision_history({
                    'env': self.env,
                    'app_name': input_data.get('app_id', 'unknown'),
                    'event_type': input_data.get('event_type', 'unknown'),

                    'decision_action': safe_action.get('action_name'),
                    'decision_source': safe_action.get('source'),
                    'confidence': safe_action.get('confidence'),

                    'executed_action': executed_action,
                    'execution_success': is_success,

                    'status': 'executed' if is_success else 'refused',

                    'reason': (
                        execution_result.get('reason') or
                        execution_result.get('error') or
                        execution_result.get('message')
                    )
                })

            except Exception as e:
                self.logger.warning(f"Decision history logging failed: {e}")


            # return {
            #     'status': 'executed' if is_success else 'refused',
            #     'action': safe_action,
            #     'execution_details': execution_result,
            #     'execution_feedback': feedback_result,
            #     'timestamp': datetime.utcnow().isoformat()
            # }

            return {
                'status': 'executed' if is_success else 'refused',

                "decision": {
                    "action": safe_action.get("action_name"),
                    "confidence": safe_action.get("confidence"),
                    "reason": safe_action.get("reason"),
                    "source": safe_action.get("source"),
                },

                "execution": {
                    "success": is_success,
                    "message": execution_result.get("message"),
                    "raw": execution_result
                },

                "app_id": input_data.get("app_id"),
                "event_type": input_data.get("event_type"),
                "timestamp": datetime.utcnow().isoformat()
            }





        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self.logger.log_error(
                "action_error",
                f"{str(e)}\n\nTraceback:\n{tb_str}",
                self.state_manager.current_state.value
            )
            print(f"[DEBUG] _act() exception: {e}")
            print(f"[DEBUG] Traceback:\n{tb_str}")
            return {'status': 'failed', 'error': str(e)}
    
    def _observe(self, action_result: Dict[str, Any]) -> Dict[str, Any]:
        """OBSERVE: Monitor action results and remember app state.
        
        Args:
            action_result: Result from act phase
            
        Returns:
            Observation of results
        """
        self.state_manager.transition_to(AgentState.OBSERVING_RESULTS, "observing_results")
        self.logger.log_state_transition(
            AgentState.ACTING.value,
            AgentState.OBSERVING_RESULTS.value,
            "observing_results"
        )
        
        try:
            # Observe system state after action
            action_data = action_result.get('action', {})
            app_id = action_data.get('input_data', {}).get('app_id', 'unknown')
            
            observation = {
                'action_status': action_result.get('status'),
                'timestamp': datetime.utcnow().isoformat(),
                'system_stable': action_result.get('status') == 'executed',
                'app_id': app_id
            }
            
            # Remember app state in memory
            if app_id != 'unknown':
                self.memory.remember_app_state(
                    app_id=app_id,
                    status='active' if observation['system_stable'] else 'unstable',
                    health={'last_action': action_result.get('status')},
                    recent_events=[
                        f"action_{action_result.get('status')}",
                        f"loop_{self.loop_count}"
                    ],
                    metrics={'timestamp': observation['timestamp']}
                )
            
            self.logger.log_observation(
                "action_result",
                observation,
                self.state_manager.current_state.value
            )
            
            return observation
        
        except Exception as e:
            self.logger.log_error(
                "observation_error",
                str(e),
                self.state_manager.current_state.value
            )
            return {'error': str(e)}
    
    def _explain(self, decision: Dict[str, Any], action_result: Dict[str, Any], observation: Dict[str, Any]):
        """EXPLAIN: Log and explain decision and results.
        
        Args:
            decision: Decision made
            action_result: Action result
            observation: Observation of results
        """
        self.state_manager.transition_to(AgentState.EXPLAINING, "explaining_decision")
        self.logger.log_state_transition(
            AgentState.OBSERVING_RESULTS.value,
            AgentState.EXPLAINING.value,
            "explaining_decision"
        )
        
        try:
            explanation = {
                'loop_count': self.loop_count,
                'decision': decision,
                'action_result': action_result,
                'observation': observation,
                'conclusion': self._generate_conclusion(decision, action_result, observation)
            }
            
            self.logger.log_autonomous_operation(
                "loop_complete_with_explanation",
                explanation,
                self.state_manager.current_state.value
            )
            
            self.logger.info(
                f"Loop {self.loop_count} complete: {explanation['conclusion']}",
                agent_state=self.state_manager.current_state.value
            )
            
            # Store for synchronous retrieval
            self._last_decision = explanation
        
        except Exception as e:
            self.logger.log_error(
                "explanation_error",
                str(e),
                self.state_manager.current_state.value
            )
    
    def _generate_conclusion(self, decision: Dict[str, Any], action_result: Dict[str, Any], observation: Dict[str, Any]) -> str:
        """Generate human-readable conclusion.
        
        Args:
            decision: Decision made
            action_result: Action result
            observation: Observation of results
            
        Returns:
            Conclusion string
        """
        action = decision.get('rl_action', 0)
        status = action_result.get('status', 'unknown')
        stable = observation.get('system_stable', False)
        
        if status == 'executed' and stable:
            return f"Successfully executed action {action}, system stable"
        elif status == 'executed':
            return f"Executed action {action}, monitoring for stability"
        else:
            return f"Action {action} {status}"
    
    def _shutdown(self):
        """Perform graceful shutdown."""
        self.logger.info(
            "Agent runtime shutting down",
            agent_state=self.state_manager.current_state.value
        )
        
        try:
            self.state_manager.transition_to(AgentState.SHUTTING_DOWN, "shutdown_requested")
            self.logger.log_state_transition(
                self.state_manager.current_state.value,
                AgentState.SHUTTING_DOWN.value,
                "shutdown_requested"
            )
        except ValueError:
            # Already in a state that can't transition to shutdown
            pass
        
        # Save state
        state_file = Path("logs/agent") / f"agent_state_{self.agent_id}.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_manager.save_to_file(str(state_file))
        
        # Save memory snapshot
        memory_file = Path("logs/agent") / f"memory_snapshot_{self.agent_id}.json"
        self.memory.to_json(str(memory_file))
        
        # Get memory stats for final log
        memory_stats = self.memory.get_memory_stats()
        
        # Log final stats
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        self.logger.log_autonomous_operation(
            "shutdown_complete",
            {
                "uptime_seconds": uptime,
                "loop_count": self.loop_count,
                "memory_stats": memory_stats,
                "proof": "autonomous_operation_verified"
            },
            AgentState.SHUTTING_DOWN.value
        )
        
        self.logger.info(
            f"Agent shutdown complete: uptime={uptime:.1f}s, loops={self.loop_count}, "
            f"decisions={memory_stats['decision_count']}, apps={memory_stats['app_count']}",
            agent_state=AgentState.SHUTTING_DOWN.value
        )

    def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status for external visibility.
        
        Returns:
            Dict containing agent state, last decision, and block information
        """
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        
        # Calculate metrics from memory
        stats = self.memory.get_memory_stats()
        total = stats.get("total_decisions_seen", 0)
        
        # Calculate rates (avoid division by zero)
        success_rate = "100%" if total == 0 else f"{(self.memory.get_memory_context().get('recent_successes', 0) / max(1, min(total, 50))) * 100:.0f}%"
        
        # Safety rate calculation
        safety_context = self.memory.get_memory_context()
        fails = safety_context.get('recent_failures', 0)
        safety_rate = "100%" if total == 0 else f"{((max(1, min(total, 50)) - fails) / max(1, min(total, 50))) * 100:.0f}%"

        autonomy_decisions_enabled = bool(self.env_config.get('autonomy_decisions_enabled', True))
        autonomy_learning_enabled = bool(self.env_config.get('autonomy_learning_enabled', self.env == 'dev'))
        env_freeze_enabled = os.getenv('EMERGENCY_FREEZE_ENABLED')
        env_freeze_reason = os.getenv('EMERGENCY_FREEZE_REASON')
        emergency_freeze_enabled = (
            str(env_freeze_enabled).lower() == 'true'
            if env_freeze_enabled is not None
            else bool(self.env_config.get('emergency_freeze_enabled', False))
        )
        emergency_freeze_reason = (
            (env_freeze_reason or '').strip()
            if env_freeze_reason is not None
            else self.env_config.get('emergency_freeze_reason', '')
        )

        autonomy_level = 'CUSTOM'
        autonomy_badge = '⚙️ CUSTOM'
        autonomy_color = 'neutral'

        if self.env == 'dev' and autonomy_decisions_enabled and autonomy_learning_enabled:
            autonomy_level = 'DEV_FULL_AUTONOMY'
            autonomy_badge = '🟢 DEV FULL'
            autonomy_color = 'green'
        elif self.env == 'stage' and autonomy_decisions_enabled and not autonomy_learning_enabled:
            autonomy_level = 'STAGE_DECISIONS_ONLY'
            autonomy_badge = '🟡 STAGE DECISIONS'
            autonomy_color = 'amber'
        elif self.env == 'prod' and autonomy_decisions_enabled and not autonomy_learning_enabled:
            autonomy_level = 'PROD_FROZEN'
            autonomy_badge = '🧊 PROD FROZEN'
            autonomy_color = 'blue'

        if emergency_freeze_enabled:
            autonomy_level = 'EMERGENCY_FREEZE'
            autonomy_badge = '🔴 EMERGENCY FREEZE'
            autonomy_color = 'red'

        status = {
            "agent_id": self.agent_id,
            "state": self.state_manager.current_state.value,
            "last_decision": self._last_decision,
            "last_block_reason": self._last_block_reason,
            "block_type": self._last_block_type,
            "loop_count": self.loop_count,
            "uptime": int(uptime),
            "uptime_seconds": int(uptime),
            "memory_stats": stats,
            "metrics": {
                "success_rate": success_rate,
                "safety_rate": safety_rate,
                "avg_response_time": "40ms" # TODO: Wire to real latency tracking
            },
            "env": self.env,
            "version": self.version,
            "timestamp": datetime.utcnow().isoformat(),
            "autonomy": {
                "level": autonomy_level,
                "badge": autonomy_badge,
                "color": autonomy_color,
                "decisions_enabled": autonomy_decisions_enabled,
                "learning_enabled": autonomy_learning_enabled,
                "emergency_freeze_enabled": emergency_freeze_enabled,
                "emergency_freeze_reason": emergency_freeze_reason
            }
        }
        
        # Add explanation if blocked
        if self._last_block_reason:
            explanations = {
                "uncertainty_too_high": "Agent refused action due to low confidence",
                "signal_conflict": "Agent entered observe-only mode due to conflicting signals",
                "cooldown_active": "Action blocked by cooldown timer",
                "repetition_suppressed": "Action blocked due to repetition limit",
                "eligibility_failed": "Action not eligible for current environment"
            }
            status["explanation"] = explanations.get(
                self._last_block_reason,
                f"Action blocked: {self._last_block_reason}"
            )
        
        return status


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Autonomous AI Agent Runtime")
    parser.add_argument("--env", type=str, choices=['dev', 'stage', 'staging', 'prod'], default='dev',
                       help='Environment to run in (default: dev)')
    parser.add_argument("--agent-id", type=str, help='Agent ID (auto-generated if not provided)')
    parser.add_argument("--loop-interval", type=float, default=5.0,
                       help='Loop interval in seconds (default: 5.0)')
    parser.add_argument("--version", action="store_true", help='Show version and exit')
    
    args = parser.parse_args()
    
    if args.version:
        print("Agent Runtime v1.0.0")
        sys.exit(0)
    
    # Create and run agent
    agent = AgentRuntime(
        env=args.env,
        agent_id=args.agent_id,
        loop_interval=args.loop_interval
    )
    
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║             AUTONOMOUS AI AGENT RUNTIME v1.0.0                   ║
╚══════════════════════════════════════════════════════════════════╝

Agent ID:       {agent.agent_id}
Environment:    {args.env}
Loop Interval:  {args.loop_interval}s
Start Time:     {agent.start_time.isoformat()}

Agent Loop: sense → validate → decide → enforce → act → observe → explain

Press Ctrl+C for graceful shutdown
""")
    
    agent.run()


if __name__ == "__main__":
    main()
