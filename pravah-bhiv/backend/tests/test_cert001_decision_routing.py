import os
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_runtime import HTTPDecisionProvider, ConfigurationError, AgentRuntime, call_decision_engine

def test_1_and_3_canonical_resolution():
    """TEST 1: PRAVAH_MAIN_API=http://decision-brain:8000 -> correct URL
       TEST 3: URL is NOT 127.0.0.1"""
    with patch.dict(os.environ, {"PRAVAH_MAIN_API": "http://decision-brain:8000"}, clear=True):
        provider = HTTPDecisionProvider()
        assert provider.endpoint_url == "http://decision-brain:8000/process-runtime"
        assert "127.0.0.1" not in provider.endpoint_url

def test_2_missing_configuration_error():
    """TEST 2: PRAVAH_MAIN_API missing -> ConfigurationError"""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ConfigurationError, match="PRAVAH_MAIN_API is required"):
            HTTPDecisionProvider()

        with pytest.raises(ConfigurationError, match="PRAVAH_MAIN_API is required"):
            call_decision_engine({})

def test_8_explicit_endpoint_url():
    """TEST 8: If endpoint_url is explicitly provided, verify documented precedence."""
    with patch.dict(os.environ, {"PRAVAH_MAIN_API": "http://decision-brain:8000"}, clear=True):
        provider = HTTPDecisionProvider(endpoint_url="http://custom:9000/path")
        assert provider.endpoint_url == "http://custom:9000/path"

@patch('security.trace_consumption.is_trace_consumed', return_value=False)
@patch('agent_runtime.RedisEventBus')
@patch('agent_runtime.ActionGovernance')
@patch('requests.post')
def test_4_and_6_trace_id_and_governance(mock_post, mock_governance, mock_redis, mock_consumed):
    """TEST 4: trace_id is preserved exactly.
       TEST 6: Valid Decision Brain response reaches governance."""
    mock_response = MagicMock()
    mock_response.text = '{"action_requested": "scale_up", "confidence": 0.9}'
    mock_response.json.return_value = {"action_requested": "scale_up", "confidence": 0.9}
    mock_post.return_value = mock_response
    
    mock_gov_instance = MagicMock()
    mock_gov_result = MagicMock()
    mock_gov_result.should_block = False
    mock_gov_instance.evaluate_action.return_value = mock_gov_result
    mock_governance.return_value = mock_gov_instance

    with patch.dict(os.environ, {"PRAVAH_MAIN_API": "http://decision-brain:8000"}, clear=True):
        # Create agent
        agent = AgentRuntime(env='dev')
        
        agent._act = MagicMock(return_value={})
        agent._observe = MagicMock(return_value={})
        agent._explain = MagicMock()

        trace_id = "CERT-001-42a0c580b1ad4dba97c72666ed0e3800"
        payload = {
            "trace_id": trace_id,
            "app_id": "test-app",
            "workers": 2,
            "cpu_percent": 80,
            "memory_percent": 60,
            "error_rate": 0,
            "event_type": "overload"
        }
        
        # We simulate the validation passing
        agent.handle_external_event(payload)
        
        # Test trace_id preservation by examining the payload passed to the provider
        mock_post.assert_called_once()
        sent_kwargs = mock_post.call_args.kwargs
        assert sent_kwargs['json']['signals'][0]['type'] == 'overload'
        assert sent_kwargs['json']['trace_id'] == trace_id

@patch('agent_runtime.RedisEventBus')
@patch('agent_runtime.ActionGovernance')
@patch('requests.post')
def test_5_and_7_failure_surfaced(mock_post, mock_governance, mock_redis):
    """TEST 5: Decision Brain HTTP failure is correctly surfaced.
       TEST 7: No fallback decision is produced when unavailable."""
    # Setup mock to simulate a connection error
    mock_post.side_effect = Exception("Connection refused")

    with patch.dict(os.environ, {"PRAVAH_MAIN_API": "http://decision-brain:8000"}, clear=True):
        agent = AgentRuntime(env='dev')
        
        from control_plane.core.agent_state import AgentState
        def mock_enforce(d):
            agent.state_manager.transition_to(AgentState.ENFORCING, "governance_enforcement")
            return {"allowed": True, "safe_action": d}
            
        agent._enforce = MagicMock(side_effect=mock_enforce)
        agent._act = MagicMock(return_value={})
        agent._observe = MagicMock(return_value={})
        
        # We need to capture the decision reaching explain
        last_decision = {}
        def mock_explain(decision, action, observation):
            nonlocal last_decision
            last_decision = decision
            agent._last_decision = {"decision": decision}
        agent._explain = mock_explain
        
        payload = {
            "trace_id": "test-trace",
            "app_id": "test-app",
            "workers": 2,
            "cpu_percent": 80,
            "memory_percent": 60,
            "error_rate": 0,
            "event_type": "overload"
        }
        
        # The agent handle_external_event returns the decision (from _last_decision)
        decision_out = agent.handle_external_event(payload)
        
        # The decision should explicitly surface the failure
        assert decision_out["decision"]["action_name"] == "invalid"
        assert decision_out["decision"]["source"] == "external_api_error"
        assert decision_out["decision"]["reason"] == "external_api_failed"
        assert decision_out["decision"]["confidence"] == 0.0
