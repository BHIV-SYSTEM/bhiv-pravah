#!/usr/bin/env python3
"""
Unified Pravah Deployment - Single Instance

Production deployment entry point that starts:
- Agent runtime (autonomous decision engine)
- API server (canonical decision endpoint + control plane)
- Proof logging (decision audit trail)

Usage:
    python deploy_pravah.py --env prod --port 7000 --workers 4
"""

import argparse
import os
import sys
import subprocess
import time
import signal
from pathlib import Path


class PravahDeployment:
    """Single unified Pravah deployment manager."""
    
    def __init__(self, env: str = "dev", port: int = 7000, workers: int = 4):
        self.env = env
        self.port = port
        self.workers = workers
        self.processes = []
        
        # Configuration
        self.root_dir = Path(__file__).parent
        self.logs_dir = self.root_dir / "logs" / "deployment"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"""
╔═══════════════════════════════════════════════════════════════╗
║           PRAVAH UNIFIED DEPLOYMENT                          ║
║          Autonomous DevOps Control Plane                     ║
╚═══════════════════════════════════════════════════════════════╝

Configuration:
  Environment:  {self.env}
  API Port:     {self.port}
  Workers:      {self.workers}
  Logs Dir:     {self.logs_dir}
        """)
    
    def setup_environment(self):
        """Configure environment variables."""
        print("[SETUP] Configuring environment...")
        
        os.environ["ENVIRONMENT"] = self.env
        os.environ["PORT"] = str(self.port)
        os.environ["PYTHONUNBUFFERED"] = "1"
        
        if self.env == "prod":
            os.environ["LOG_LEVEL"] = "INFO"
        else:
            os.environ["LOG_LEVEL"] = "DEBUG"
        
        print("  ✓ Environment configured")
    
    def start_agent_runtime(self):
        """Start autonomous agent runtime."""
        print("[RUNTIME] Starting agent runtime...")
        
        log_file = self.logs_dir / "agent_runtime.log"
        
        cmd = [
            sys.executable,
            "agent_runtime.py",
            f"--env={self.env}",
        ]
        
        with open(log_file, "w") as log_fh:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                cwd=str(self.root_dir),
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
            )
        
        self.processes.append(("agent_runtime", proc))
        print(f"  ✓ Runtime started (PID {proc.pid})")
        print(f"  ✓ Logs: {log_file}")
        
        time.sleep(2)  # Give runtime time to initialize
    
    def start_api_server(self):
        """Start production API server."""
        print("[API] Starting API server...")
        
        log_file = self.logs_dir / "api_server.log"
        
        # Use gunicorn for production, flask development for dev
        if self.env == "prod":
            cmd = [
                "gunicorn",
                "-w", str(self.workers),
                "-b", f"0.0.0.0:{self.port}",
                "--access-logfile", str(log_file),
                "--error-logfile", str(log_file),
                "--log-level", "info",
                "control_plane.api.agent_api:app",
            ]
        else:
            cmd = [
                sys.executable,
                "-c",
                f"from control_plane.api.agent_api import app; app.run(host='0.0.0.0', port={self.port}, debug={self.env == 'dev'})",
            ]
        
        with open(log_file, "w") as log_fh:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                cwd=str(self.root_dir),
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
            )
        
        self.processes.append(("api_server", proc))
        print(f"  ✓ API started (PID {proc.pid})")
        print(f"  ✓ Logs: {log_file}")
        print(f"  ✓ Access: http://localhost:{self.port}/api/health")
        
        time.sleep(2)  # Give API time to start
    
    def health_check(self):
        """Verify deployment health."""
        print("[HEALTH] Checking deployment health...")
        
        import requests
        
        health_url = f"http://localhost:{self.port}/api/health"
        
        for attempt in range(5):
            try:
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    print("  ✓ Health check passed")
                    print(f"  ✓ API responding at {health_url}")
                    return True
            except Exception:
                pass
            
            if attempt < 4:
                print(f"  ⏳ Waiting for API... (attempt {attempt + 1}/5)")
                time.sleep(1)
        
        print("  ⚠️ Health check timeout - API may not be ready")
        return False
    
    def display_status(self):
        """Display deployment status."""
        print("\n" + "="*60)
        print("PRAVAH DEPLOYMENT STATUS")
        print("="*60)
        
        for name, proc in self.processes:
            status = "✓ RUNNING" if proc.poll() is None else "✗ STOPPED"
            print(f"  {name:20} {status} (PID {proc.pid})")
        
        print("\nAccess Points:")
        print(f"  API Health:              http://localhost:{self.port}/api/health")
        print(f"  Agent Status:            http://localhost:{self.port}/api/status")
        print(f"  Control Plane Dashboard: http://localhost:{self.port}/api/control-plane/health")
        print(f"  Decision History:        http://localhost:{self.port}/api/control-plane/history/<app>")
        
        print("\nLogs Directory:")
        print(f"  {self.logs_dir}")
        
        print("\n" + "="*60)
        print("Deployment ready. Press Ctrl+C to stop.")
        print("="*60 + "\n")
    
    def run(self):
        """Execute deployment."""
        try:
            self.setup_environment()
            self.start_agent_runtime()
            self.start_api_server()
            self.health_check()
            self.display_status()
            
            # Keep running
            while True:
                time.sleep(1)
        
        except KeyboardInterrupt:
            print("\n\n[SHUTDOWN] Stopping Pravah deployment...")
            self.cleanup()
        
        except Exception as e:
            print(f"\n[ERROR] Deployment failed: {str(e)}")
            self.cleanup()
            return 1
        
        return 0
    
    def cleanup(self):
        """Clean up processes."""
        print("[CLEANUP] Terminating processes...")
        
        for name, proc in self.processes:
            if proc.poll() is None:
                try:
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    else:
                        proc.terminate()
                    print(f"  ✓ Stopped {name} (PID {proc.pid})")
                except Exception as e:
                    print(f"  ⚠️ Failed to stop {name}: {str(e)}")
        
        print("[CLEANUP] Pravah deployment stopped")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Pravah Unified Deployment - Single Instance"
    )
    parser.add_argument(
        "--env",
        choices=["dev", "staging", "prod"],
        default="dev",
        help="Deployment environment"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7000,
        help="API server port"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of API workers (production only)"
    )
    
    args = parser.parse_args()
    
    deployment = PravahDeployment(env=args.env, port=args.port, workers=args.workers)
    return deployment.run()


if __name__ == "__main__":
    sys.exit(main())
