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
print("[2] Importing Flask...")
from flask import Flask, jsonify, request
print("[3] Importing AgentRuntime...")
from agent_runtime import AgentRuntime
print("[4] Instantiating AgentRuntime...")
agent = AgentRuntime(env="dev")
print("[5] Instantiating MultiAppControlPlane...")
from control_plane.multi_app_control_plane import MultiAppControlPlane
control_plane = MultiAppControlPlane(env="dev")
print("[6] Spawning background thread...")
import threading
def loop():
    print("[THREAD] Thread loop started!")
    agent.run()
threading.Thread(target=loop, daemon=True).start()
print("[7] All done!")
