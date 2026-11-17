#!/usr/bin/env python3
import os
import sys

print("[DEBUG] CWD:", os.getcwd())
print("[DEBUG] Adding paths to sys.path...")

root_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
control_plane_dir = os.path.join(root_dir, 'control_plane')

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if control_plane_dir not in sys.path:
    sys.path.insert(1, control_plane_dir)

print("[DEBUG] sys.path updated. Importing app from api.agent_api...")
try:
    from api.agent_api import app
    print("[DEBUG] Import successful! Starting Flask app...")
    app.run(host='0.0.0.0', port=7000, debug=False)
except Exception as e:
    import traceback
    print("[DEBUG] CRITICAL EXCEPTION:")
    traceback.print_exc()
