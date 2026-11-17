#!/usr/bin/env python3
"""App Orchestrator - Deploy, Stop, Scale applications"""
import json
import os
import subprocess
import time
from typing import Dict, Any, Optional
from agents.deploy_agent import DeployAgent
from build.build_engine import BuildEngine

class AppOrchestrator:
    """Orchestrates application lifecycle: deploy, stop, scale."""
    
    def __init__(self, env='dev'):
        self.env = env
        self.build_engine = BuildEngine()
        self.deploy_agent = DeployAgent('deployment_log.csv', env=env, worker_id=1)
        self.state_file = f'orchestrator/app_state_{env}.json'
        self._ensure_log_dirs()
        self._load_state()
    
    def _ensure_log_dirs(self):
        """Ensure app-specific log directories exist."""
        os.makedirs(f'logs/{self.env}', exist_ok=True)
    
    def _log_app_deployment(self, app_name: str, status: str, response_time: float, action: str):
        """Log app-specific deployment."""
        import csv
        import datetime
        
        log_file = f'logs/{self.env}/{app_name}_deployment_log.csv'
        
        if not os.path.exists(log_file):
            with open(log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'app_name', 'action', 'status', 'response_time_ms', 'environment'])
        
        with open(log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.datetime.now().isoformat(), app_name, action, status, response_time, self.env])
    
    def _log_app_health(self, app_name: str, healthy: bool, workers: int):
        """Log app-specific health."""
        import csv
        import datetime
        
        log_file = f'logs/{self.env}/{app_name}_health_log.csv'
        
        if not os.path.exists(log_file):
            with open(log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'app_name', 'healthy', 'workers', 'environment'])
        
        with open(log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.datetime.now().isoformat(), app_name, healthy, workers, self.env])
    
    def _load_state(self):
        """Load current app state."""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
        else:
            self.state = {'apps': {}}
    
    def _save_state(self):
        """Save current app state."""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def deploy_app(self, app_name: str, env: str = None) -> Dict[str, Any]:
        """Deploy application to environment."""
        env = env or self.env
        
        print(f"🚀 Deploying {app_name} to {env.upper()}")
        
        # Get build from registry
        build = self.deploy_agent.get_build_from_registry(app_name)

        # If no build exists, create one
        if not build:
            print(f"🔧 No build found for {app_name}, creating build...")

            spec_file = f"apps/registry/{app_name}.json"

            if not os.path.exists(spec_file):
                return {'success': False, 'error': f'App spec not found for {app_name}'}

            with open(spec_file) as f:
                spec = json.load(f)

            repo_url = spec.get("repo_path_or_url")

            build_result = self.build_engine.build(repo_url, app_name)

            if not build_result["success"]:
                return {'success': False, 'error': build_result["error"]}

            print(f"✅ Build created for {app_name}")

            # Try retrieving build again


        build = {
            "build_id": f"{app_name}_build",
            "build_path": f"build_workspace/{app_name}"
        }



        # Deploy using deploy agent



        result = self.deploy_agent.deploy_from_build(
            app_name,
            build_path=build["build_path"]
        )



        if result['success']:
            # Update state
            self.state['apps'][app_name] = {
                'status': 'running',
                'environment': env,
                'build_id': build['build_id'],
                'workers': 1,
                'deployed_at': time.time()
            }
            self._save_state()
            
            # Log app-specific deployment
            self._log_app_deployment(app_name, 'success', result['response_time'], 'deploy')
            self._log_app_health(app_name, True, 1)
            
            print(f"✅ {app_name} deployed successfully")
        
        return result
    
    def stop_app(self, app_name: str, env: str = None) -> Dict[str, Any]:
        """Stop running application."""
        env = env or self.env
        
        print(f"🛑 Stopping {app_name} in {env.upper()}")
        
        if app_name not in self.state['apps']:
            return {'success': False, 'error': f'{app_name} not found in state'}
        
        app_state = self.state['apps'][app_name]
        
        # Try multiple stop methods
        stopped = False
        method = 'state_only'
        
        try:
            # Method 1: docker-compose
            result = subprocess.run(
                ['docker-compose', 'stop', app_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                stopped = True
                method = 'docker-compose'
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        if not stopped:
            try:
                # Method 2: docker stop by name
                result = subprocess.run(
                    ['docker', 'stop', app_name],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    stopped = True
                    method = 'docker'
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        
        # Update state regardless
        app_state['status'] = 'stopped'
        app_state['stopped_at'] = time.time()
        app_state['stop_method'] = method
        self._save_state()
        
        # Log app-specific health
        self._log_app_health(app_name, False, 0)
        
        print(f"✅ {app_name} stopped (method: {method})")
        return {'success': True, 'app_name': app_name, 'status': 'stopped', 'method': method}
    
    def scale_app(self, app_name: str, workers: int, env: str = None) -> Dict[str, Any]:
        """Scale application to specified number of workers."""
        env = env or self.env
        
        print(f"📈 Scaling {app_name} to {workers} workers in {env.upper()}")
        
        if app_name not in self.state['apps']:
            return {'success': False, 'error': f'{app_name} not deployed'}
        
        app_state = self.state['apps'][app_name]
        current_workers = app_state.get('workers', 1)
        
        if workers < 1:
            return {'success': False, 'error': 'Workers must be >= 1'}
        
        # Try docker-compose scaling
        scaled = False
        method = 'state_only'
        
        try:
            result = subprocess.run(
                ['docker-compose', 'up', '-d', '--scale', f'{app_name}={workers}'],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                scaled = True
                method = 'docker-compose'
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Update state
        app_state['workers'] = workers
        app_state['scaled_at'] = time.time()
        app_state['scale_method'] = method
        self._save_state()
        
        # Log app-specific health
        self._log_app_health(app_name, True, workers)
        
        print(f"✅ {app_name} scaled from {current_workers} to {workers} workers (method: {method})")
        
        return {
            'success': True,
            'app_name': app_name,
            'previous_workers': current_workers,
            'current_workers': workers,
            'method': method
        }
    
    def get_app_status(self, app_name: str) -> Optional[Dict[str, Any]]:
        """Get current status of application."""
        return self.state['apps'].get(app_name)
    
    def list_apps(self) -> Dict[str, Any]:
        """List all managed applications."""
        return self.state['apps']

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="App Orchestrator")
    parser.add_argument("--env", default="dev", choices=['dev', 'stage', 'prod'])
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy application')
    deploy_parser.add_argument('app_name', help='Application name')
    
    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Stop application')
    stop_parser.add_argument('app_name', help='Application name')
    
    # Scale command
    scale_parser = subparsers.add_parser('scale', help='Scale application')
    scale_parser.add_argument('app_name', help='Application name')
    scale_parser.add_argument('workers', type=int, help='Number of workers')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List applications')
    
    args = parser.parse_args()
    
    orchestrator = AppOrchestrator(args.env)
    
    if args.command == 'deploy':
        result = orchestrator.deploy_app(args.app_name, args.env)
        exit(0 if result['success'] else 1)
    
    elif args.command == 'stop':
        result = orchestrator.stop_app(args.app_name, args.env)
        exit(0 if result['success'] else 1)
    
    elif args.command == 'scale':
        result = orchestrator.scale_app(args.app_name, args.workers, args.env)
        exit(0 if result['success'] else 1)
    
    elif args.command == 'list':
        apps = orchestrator.list_apps()
        print(f"\n📋 Applications in {args.env.upper()}:")
        for app_name, state in apps.items():
            print(f"  • {app_name}: {state['status']} ({state.get('workers', 1)} workers)")
        exit(0)
    
    else:
        parser.print_help()
        exit(1)