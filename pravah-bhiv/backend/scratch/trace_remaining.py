#!/usr/bin/env python3
import os
import sys

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if os.path.join(root_dir, 'control_plane') not in sys.path:
    sys.path.insert(1, os.path.join(root_dir, 'control_plane'))

print("[1] Importing requests...")
import requests

print("[2] Importing agent_state...")
from control_plane.core.agent_state import AgentState, AgentStateManager

print("[3] Importing agent_logger...")
from control_plane.core.agent_logger import AgentLogger

print("[4] Importing agent_memory...")
from control_plane.core.agent_memory import AgentMemory

print("[5] Importing perception...")
from control_plane.core.perception import PerceptionLayer

print("[6] Importing perception_adapters...")
from control_plane.core.perception_adapters import (
    RuntimeEventAdapter,
    HealthSignalAdapter,
    OnboardingInputAdapter,
    SystemAlertAdapter
)

print("[7] Importing ActionGovernance...")
from control_plane.core.action_governance import ActionGovernance

print("[8] Importing proof_logger...")
from control_plane.core.proof_logger import write_proof, ProofEvents

print("[9] Importing env_config...")
from control_plane.core.env_config import EnvironmentConfig

print("[10] Importing rl_orchestrator_safe...")
from control_plane.core.rl_orchestrator_safe import get_safe_executor

print("[11] Importing multi_deploy_agent...")
from control_plane.agents.multi_deploy_agent import MultiDeployAgent

print("[12] Importing RedisEventBus...")
from control_plane.core.redis_event_bus import RedisEventBus

print("[13] Importing EventBus...")
from control_plane.core.event_bus import EventBus

print("[14] Importing UptimeMonitor...")
from control_plane.agents.uptime_monitor import UptimeMonitor

print("[15] All done!")
