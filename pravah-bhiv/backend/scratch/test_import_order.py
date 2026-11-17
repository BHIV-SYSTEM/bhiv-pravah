#!/usr/bin/env python3
import os
import sys

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if os.path.join(root_dir, 'control_plane') not in sys.path:
    sys.path.insert(1, os.path.join(root_dir, 'control_plane'))

print("[1] Importing UptimeMonitor first...")
from control_plane.agents.uptime_monitor import UptimeMonitor
print("[2] Importing the rest of the modules...")
from agent_runtime import AgentRuntime
print("[3] All done!")
