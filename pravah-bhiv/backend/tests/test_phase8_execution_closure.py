import pytest
import os
import sys
from unittest.mock import patch, MagicMock

os.environ["PRAVAH_MAIN_API"] = "http://example.com"

# Prevent main.py from hanging on global AgentRuntime initialization
sys.modules['control_plane.backend.app.integration_bridge'] = MagicMock()

from control_plane.backend.app.main import execute_action
from agent_runtime import AgentRuntime
from control_plane.core.rl_orchestrator_safe import SafeOrchestrator

# =======================================================
# TEST A & B: API PATH CLOSURE (Execution Rights Adapter)
# =======================================================
@pytest.mark.asyncio
async def test_api_missing_capability():
    """Test A: API path succeeds when capability is internally mapped and authorized.
    
    Proves: execute_action internally associates the capability, calls the real 
    authorize_execution, creates the real execution contract, evaluates real 
    ActionGovernance, and succeeds without mocking any of the security boundaries.
    """
    # Only mock the final side effect (the actual executor request) and signing 
    # to avoid needing the private key in the test environment.
    with patch("requests.post") as mock_post, \
         patch("security.signed_trace.sign_trace", return_value="mock_sig"), \
         patch("security.signed_trace.canonicalize", return_value="mock_canon"):
        
        def mock_resp(*args, **kwargs):
            req_json = kwargs.get("json", {})
            mock_obj = MagicMock()
            mock_obj.status_code = 200
            mock_obj.json.return_value = {
                "status": "accepted",
                "execution_id": req_json.get("execution_id"),
                "action": req_json.get("action"),
                "service_id": req_json.get("service_id"),
                "trace_id": req_json.get("trace_id"),
                "execution_hash": req_json.get("execution_hash"),
                "capability_id": req_json.get("capability_id"),
                "reason": "Mock action accepted",
                "verified": False,
            }
            return mock_obj

        mock_post.side_effect = mock_resp
        
        allowed, response = execute_action(
            action="restart",
            service_id="app01"
        )
        
        # Expect allowed execution with accepted status
        assert allowed is True
        assert response["status"] == "accepted"
        mock_post.assert_called()


@pytest.mark.asyncio
async def test_api_unmapped_capability():
    """Test B: API path rejects when the action lacks a verified mapping.
    
    Proves: A genuinely unmapped capability is rejected by the real authorize_execution.
    """
    with patch("requests.post") as mock_post, \
         patch("control_plane.capabilities.execution_rights_adapter.VERIFIED_CAPABILITY_MAPPINGS", {}):

        allowed, response = execute_action(
            action="restart",
            service_id="app01"
        )

        assert allowed is False
        assert response["status"] == "rejected"
        assert "No verified Execution Rights mapping" in response["reason"]
        mock_post.assert_not_called()

# =======================================================
# TEST C: AGENT RUNTIME CLOSURE (Action Governance)
# =======================================================
def test_agent_runtime_unmapped_capability():
    """Test C: Agent Runtime blocks state changing actions using real governance.
    
    Proves: AgentRuntime._enforce() uses the real ActionGovernance boundary to block 
    unallowed actions (like scale_up in the default env if restricted, or invalid actions).
    No executors are reached, and authorize_execution is not mocked (as it is not used here).
    """
    # Components already mocked at the module level
    with patch.object(AgentRuntime, '_initialize_components'):
        runtime = AgentRuntime(env="prod")
        
        decision = {
            "rl_action": 2, # 2 maps to "scale_up"
            "action_name": "scale_up",
            "input_data": {"app_id": "app01"}
        }
        
        # In prod, scale_up is NOT eligible in ActionGovernance.
        # It should return allowed: False with reason: 'action_not_eligible'
        
        # Need to transition to DECIDING before ENFORCING to pass the state machine
        from control_plane.core.agent_state import AgentState
        runtime.state_manager._current_state = AgentState.DECIDING
        
        result = runtime._enforce(decision)
        
        assert result["allowed"] is False
        assert result["block_type"] == "governance"
        assert result["reason"] == "action_not_eligible"

# =======================================================
# TEST D: RL ORCHESTRATOR CLOSURE (Production vs Demo Mode)
# =======================================================
def test_rl_orchestrator_production_mode():
    """Test D1: SafeOrchestrator in prod environment blocks unsafe actions.
    
    Proves: env="prod" natively restricts actions (e.g. scale_up) via ActionGovernance
    eligibility rules, which executes before execution gates.
    """
    # We patch advance_execution_state just in case it reaches there, but it shouldn't.
    with patch("control_plane.core.rl_orchestrator_safe.advance_execution_state") as mock_exec_state:
        orch = SafeOrchestrator(env="prod")
        
        decision = {
            "decision_type": "execution",
            "action": "scale_up",  # scale_up is not eligible in prod
            "parameters": {"app_name": "app01", "source": "legacy"},
            "version": "v1"
        }
        
        result = orch.execute_decision_contract(decision, context={"app_name": "app01"}, source="legacy")
        
        assert result.get("success") is False
        assert result.get("refused") is True
        # It hits ActionGovernance first which rejects it
        assert result.get("reason_code") == "action_not_eligible"
        mock_exec_state.assert_not_called()

def test_rl_orchestrator_demo_mode():
    """Test D2: SafeOrchestrator demo mode (simulation) rules.
    
    Proves: The orchestrator's real DEMO_MODE logic enforces that actions MUST come 
    from the rl_decision_layer source, else they are blocked by the intake gate.
    """
    # We simulate demo mode being active
    from contracts.execution_contract import ExecutionContract
    with patch("control_plane.core.rl_orchestrator_safe.advance_execution_state") as mock_advance, \
         patch.object(SafeOrchestrator, '__init__', lambda self, env='dev': None):
         
        mock_advance.return_value = ExecutionContract(
            execution_id="mock_exec_id", 
            decision_id="mock_decision_id",
            decision_contract={"decision_type": "execution", "action": "restart", "parameters": {"app_name": "app01"}, "version": "v1"},
            execution_payload={},
            status="authorized",
            execution_hash="mock_exec_hash", 
            approved_at=1234567890,
            approved_by="mock_approved_by",
            execution_state="APPROVED",
            immutable=True
        )
        
        orch = SafeOrchestrator()
        orch.env = "prod"
        orch.demo_mode = True
        orch.demo_enforce_prod = True
        orch.safe_actions = {'restart': lambda ctx: {'success': True}}
        orch.safety_rules = {'prod': ['noop', 'restart']}
        
        decision = {
            "decision_type": "execution",
            "action": "restart",
            "parameters": {"app_name": "app01"},
            "version": "v1"
        }
        
        with patch("control_plane.core.action_governance.ActionGovernance") as mock_gov:
            decision_mock = MagicMock()
            decision_mock.should_block = False
            decision_mock.reason = None
            decision_mock.policy_id = "mock_policy"
            decision_mock.policy_version = "v1"
            decision_mock.policy_hash = "mock_hash"
            mock_gov.return_value.evaluate_contract.return_value = decision_mock
            mock_gov.return_value.evaluate_action.return_value = decision_mock
            
            # Test Demo Mode Gate: Blocked if source is NOT rl_decision_layer
            # We MUST provide app_name in context so it passes the prerequisite check in ActionGovernance
            result_blocked = orch.execute_decision_contract(decision, context={"app_name": "app01"}, source="legacy")
            assert result_blocked.get("refused") is True
            assert result_blocked.get("reason_code") == "demo_mode_gate_blocked"
            
            # Test Demo Mode Gate: Allowed if source IS rl_decision_layer (and it's a safe action)
            result_allowed = orch.execute_decision_contract(decision, context={"app_name": "app01"}, source="rl_decision_layer")
            assert result_allowed.get("success") is True
            assert result_allowed.get("action_executed") == "restart"
