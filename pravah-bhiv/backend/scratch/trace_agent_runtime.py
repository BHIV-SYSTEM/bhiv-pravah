#!/usr/bin/env python3
import os
import sys

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if os.path.join(root_dir, 'control_plane') not in sys.path:
    sys.path.insert(1, os.path.join(root_dir, 'control_plane'))

print("[A] Importing requests...")
import requests
print("[B] Importing agent_state...")
from control_plane.core.agent_state import AgentState, AgentStateManager
print("[C] Importing agent_logger...")
from control_plane.core.agent_logger import AgentLogger
print("[D] Importing agent_memory...")
from control_plane.core.agent_memory import AgentMemory
print("[E] Importing perception...")
from control_plane.core.perception import PerceptionLayer
print("[F] Importing perception_adapters...")
from control_plane.core.perception_adapters import (
    RuntimeEventAdapter,
    HealthSignalAdapter,
    OnboardingInputAdapter,
    SystemAlertAdapter
)
print("[G] Importing action_governance...")
from control_plane.core.action_governance import ActionGovernance
print("[H] Importing proof_logger...")
from control_plane.core.proof_logger import write_proof, ProofEvents
print("[I] Importing env_config...")
from control_plane.core.env_config import EnvironmentConfig
print("[J] Importing rl_orchestrator_safe...")
from control_plane.core.rl_orchestrator_safe import get_safe_executor
print("[K] Importing multi_deploy_agent...")
from control_plane.agents.multi_deploy_agent import MultiDeployAgent
print("[L] Importing redis_event_bus...")
from control_plane.core.redis_event_bus import RedisEventBus
print("[M] Importing event_bus...")
from control_plane.core.event_bus import EventBus
print("[N] Importing uptime_monitor...")
from control_plane.agents.uptime_monitor import UptimeMonitor
print("[O] Importing runtime_event_validator...")
from control_plane.core.runtime_event_validator import RuntimeEventValidator
print("[P] All imported successfully!")
