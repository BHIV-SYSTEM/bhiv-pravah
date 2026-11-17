
from unittest.mock import patch, MagicMock
from agent_runtime import AgentRuntime
import traceback

def test_init():
    print("Attempting AgentRuntime initialization...")
    with patch('agent_runtime.MultiDeployAgent'), \
         patch('agent_runtime.RedisEventBus'):
        try:
            agent = AgentRuntime(env='dev', loop_interval=0)
            print("Initialization successful!")
            
            # Test a small decision loop
            print("Testing _decide...")
            mock_data = {"event_type": "high_cpu", "cpu_usage": 90, "app_id": "test-app"}
            decision = agent._decide(mock_data)
            print(f"Decision: {decision['action_name']} from {decision['source']}")
            
        except Exception as e:
            print("Initialization failed!")
            traceback.print_exc()

if __name__ == "__main__":
    test_init()
