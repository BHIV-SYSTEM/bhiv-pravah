# observer_launcher.py
"""Entry point for the Pravah Bhiv observer runtime.
It accepts target service URLs and starts the observer web server (`observer_server.py`).
The observer UI will be available on port 8600 (default).
"""

import os
import sys
import subprocess
import argparse
import signal
import threading
import time

def parse_args():
    parser = argparse.ArgumentParser(description="Start Pravah Bhiv observer with service endpoints")
    parser.add_argument("--crm-api", help="CRM API base URL", required=False)
    parser.add_argument("--main-api", help="Main API base URL", required=False)
    parser.add_argument("--crm-dashboard", help="CRM Dashboard URL", required=False)
    parser.add_argument("--main-dashboard", help="Main Dashboard URL", required=False)
    parser.add_argument("--port", type=int, default=8600, help="Port for observer UI")
    parser.add_argument("--ui", action="store_true", help="Enable observer web UI")
    return parser.parse_args()

def start_observer(args):
    env = os.environ.copy()
    if args.crm_api:
        env["PRAVAH_CRM_API"] = args.crm_api
    if args.main_api:
        env["PRAVAH_MAIN_API"] = args.main_api
    if args.crm_dashboard:
        env["PRAVAH_CRM_DASHBOARD"] = args.crm_dashboard
    if args.main_dashboard:
        env["PRAVAH_MAIN_DASHBOARD"] = args.main_dashboard
    env["PRAVAH_OBSERVER_PORT"] = str(args.port)
    env["PRAVAH_OBSERVER_UI"] = "1" if args.ui else "0"
    observer_script = os.path.join(os.path.dirname(__file__), "observer_server.py")
    cmd = [sys.executable, observer_script]
    process = subprocess.Popen(cmd, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process

def stream_output(prefix, pipe):
    for line in iter(pipe.readline, b''):
        print(f"[{prefix}] {line.decode().rstrip()}")
    pipe.close()

def shutdown(signum, frame, proc):
    print(f"\n[Shutdown] Received signal {signum}, shutting down observer...")
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
            print("✅ Observer stopped")
        except subprocess.TimeoutExpired:
            print("⚠️ Force killing observer...")
            proc.kill()
    sys.exit(0)

if __name__ == "__main__":
    args = parse_args()
    observer_proc = start_observer(args)
    threading.Thread(target=stream_output, args=("Observer", observer_proc.stdout), daemon=True).start()
    threading.Thread(target=stream_output, args=("Observer", observer_proc.stderr), daemon=True).start()
    signal.signal(signal.SIGINT, lambda s, f: shutdown(s, f, observer_proc))
    signal.signal(signal.SIGTERM, lambda s, f: shutdown(s, f, observer_proc))
    try:
        while observer_proc.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(signal.SIGINT, None, observer_proc)
