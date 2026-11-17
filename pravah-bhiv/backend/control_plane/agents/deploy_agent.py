import os
import csv
import datetime
import json
from control_plane.core.redis_event_bus import get_redis_bus
from control_plane.core.metrics_collector import get_metrics_collector
from integration.event_schema import StandardEvent
from control_plane.core.env_config import EnvironmentConfig

class DeployAgent:
    """Tracks and logs main deployment events to a CSV file."""
    def __init__(self, log_file, env='dev', worker_id=1, build_registry='build/build_registry.json'):
        self.env = env
        self.worker_id = worker_id
        self.build_registry = build_registry
        self.env_config = EnvironmentConfig(env)
        self.redis_bus = get_redis_bus(env)
        self.metrics = get_metrics_collector(env)
        
        # Add worker ID to log file name
        base_name = os.path.basename(log_file)
        name, ext = os.path.splitext(base_name)
        worker_log_name = f"{name}_worker_{worker_id}{ext}"
        self.log_file = self.env_config.get_log_path(worker_log_name)
        
        self._initialize_log_file()
        print(f"Initialized Deploy Agent Worker {worker_id} for {env.upper()} environment.")

    def _initialize_log_file(self):
        """Creates the log file with a header if it doesn't exist."""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["timestamp", "dataset_changed", "status", "response_time_ms", "action_type", "environment", "worker_id", "app_name", "build_id"])

    def get_build_from_registry(self, app_name: str) -> dict | None:
        """Get latest build for app from build registry."""
        try:
            if os.path.exists(self.build_registry):
                with open(self.build_registry, 'r') as f:
                    registry = json.load(f)
                
                builds = [b for b in registry['builds'] 
                         if b['app_name'] == app_name and b['environment'] == self.env and b['build_status'] == 'success']
                
                return builds[-1] if builds else None
        except Exception:
            pass
        return None
    
    def log_deployment(self, dataset, status, response_time, action_type="deploy", app_name=None, build_id=None):
        """Logs a single event to the deployment log file."""
        timestamp = datetime.datetime.now().isoformat()
        with open(self.log_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, dataset, status, round(response_time, 2), action_type, self.env, self.worker_id, app_name or "legacy", build_id or "N/A"])
        app_info = f" [{app_name}]" if app_name else ""
        print(f"[{self.env.upper()}-W{self.worker_id}] Logged {action_type}{app_info} for {os.path.basename(dataset)}: {status} ({round(response_time,2)} ms)")
        
        # Publish standardized event
        event_type = f"deploy.{status}" if action_type == "deploy" else f"heal.{status}"
        std_event = StandardEvent.from_deployment(
            self.env, status, response_time, dataset, action_type, self.worker_id
        )
        self.redis_bus.publish(event_type, std_event.to_dict())
        
        # Record metrics
        service_name = f"deploy_agent_worker_{self.worker_id}"
        self.metrics.record_latency_metric(service_name, action_type, response_time)
        
        # Record deployment success rate
        if action_type == "deploy":
            success_count = 1 if status == "success" else 0
            fail_count = 1 if status == "failure" else 0
            self.metrics.record_deploy_success_rate(1, success_count, fail_count, response_time)
    
    def deploy_from_build(self, app_name: str, build_path: str | None = None) -> dict:
        """Deploy application using registry build OR local build workspace."""

        # CASE 1 — Deploy from local build workspace
        if build_path:
            print(f"🚀 Deploying {app_name} from local build path: {build_path}")

            import time
            start = time.time()
            time.sleep(0.5)

            response_time = (time.time() - start) * 1000

            self.log_deployment(
                dataset=build_path,
                status="success",
                response_time=response_time,
                action_type="deploy",
                app_name=app_name,
                build_id="local_build"
            )

            return {
                "success": True,
                "app_name": app_name,
                "build_id": "local_build",
                "image": build_path,
                "response_time": response_time
            }

        # CASE 2 — Deploy from registry
        build = self.get_build_from_registry(app_name)

        if not build:
            return {'success': False, 'error': f'No build found for {app_name} in {self.env}'}

        print(f"🚀 Deploying {app_name} from build: {build['build_id']}")
        print(f"   Image: {build['image_name']}")

        import time
        start = time.time()
        time.sleep(0.5)

        response_time = (time.time() - start) * 1000

        status = 'success'
        self.log_deployment(build['image_name'], status, response_time, 'deploy', app_name, build['build_id'])

        return {
            'success': True,
            'app_name': app_name,
            'build_id': build['build_id'],
            'image': build['image_name'],
            'response_time': response_time
        }