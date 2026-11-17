#!/usr/bin/env python3
"""
Onboarding Entry Layer - Text to Spec Conversion
Converts simple text input to validated app_spec.json

Principles:
- No intelligence/inference/guessing
- Template-based conversion only
- Deterministic validation
- Clear error messages
"""

import json
import os
import re
import sys
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, Any, Optional

class OnboardingEntry:
    def __init__(self):
        self.output_dir = "apps/registry"
        self.registry_index_file = os.path.join(self.output_dir, "registry_index.jsonl")
        self.log_file = "logs/onboarding.log"
        self.proof_log = "logs/onboarding_proof.log"
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        self.last_error = None
        
        # Import proof logger
        try:
            from core.proof_logger import write_proof, ProofEvents
            self.proof_logger = write_proof
            self.ProofEvents = ProofEvents
            self.use_proof_logging = True
        except ImportError:
            self.use_proof_logging = False
    
    def process(self, repo_url: str, app_name: str, runtime_type: str) -> bool:
        """Convert input to app_spec.json with validation"""
        source_url = self._normalize_source_url(repo_url)
        
        # Log onboarding start
        self._log_proof(self.ProofEvents.ONBOARDING_STARTED if self.use_proof_logging else None, {
            'app_name': app_name,
            'runtime_type': runtime_type,
            'repo_url': source_url[:100]  # Truncate for logging
        })
        
        # Validate input (deterministic, no guessing)
        is_valid, error_message = self._validate_input(source_url, app_name, runtime_type)
        if not is_valid:
            self.last_error = error_message
            self._log_proof(self.ProofEvents.ONBOARDING_REJECTED if self.use_proof_logging else None, {
                'app_name': app_name,
                'reason': error_message
            })
            self._log("REJECTED", {"repo_url": source_url, "app_name": app_name, "runtime_type": runtime_type}, error_message)
            return False
        
        # Log validation passed
        self._log_proof(self.ProofEvents.ONBOARDING_VALIDATION_PASSED if self.use_proof_logging else None, {
            'app_name': app_name,
            'runtime_type': runtime_type
        })
        
        # Generate app_spec (template-based, no intelligence)
        app_spec = self._generate_spec(source_url, app_name, runtime_type)
        
        # Save to registry (persistent storage)
        output_file = self._save_spec(app_name, app_spec)
        
        # Log spec generated
        self._log_proof(self.ProofEvents.SPEC_GENERATED if self.use_proof_logging else None, {
            'app_name': app_name,
            'spec_file': output_file
        })
        
        self._log("ACCEPTED", {"repo_url": source_url, "app_name": app_name, "runtime_type": runtime_type}, output_file)
        
        # Trigger deployment
        self._trigger_deployment(app_name, output_file)
        
        return True

    def _normalize_source_url(self, source_url: str) -> str:
        """Normalize URL deterministically for canonical app_spec output."""
        url = source_url.strip()
        parsed = urlparse(url)

        scheme = parsed.scheme.lower()
        host = parsed.netloc.lower()
        path = parsed.path or "/"

        if host == "github.com":
            segments = [segment for segment in path.strip('/').split('/') if segment]
            if len(segments) >= 2:
                owner = segments[0]
                repository = segments[1].removesuffix('.git')
                return f"{scheme}://{host}/{owner}/{repository}"

        normalized = f"{scheme}://{host}{path}"
        return normalized[:-1] if normalized.endswith('/') and path != '/' else normalized

    def _save_spec(self, app_name: str, app_spec: Dict[str, Any]) -> str:
        """Persist app spec and append durable registry index entry."""
        output_file = os.path.join(self.output_dir, f"{app_name}.json")

        with open(output_file, 'w', encoding='utf-8') as spec_file:
            json.dump(app_spec, spec_file, indent=2)

        registry_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "app_name": app_name,
            "spec_file": output_file,
            "source_type": app_spec.get("source_type"),
            "repo_path_or_url": app_spec.get("repo_path_or_url")
        }

        with open(self.registry_index_file, 'a', encoding='utf-8') as index_file:
            index_file.write(json.dumps(registry_entry) + "\n")

        return output_file
    
    def _validate_input(self, repo_url: str, app_name: str, runtime_type: str) -> tuple[bool, Optional[str]]:
        """Validate input parameters (deterministic, no guessing)
        
        Returns:
            tuple: (is_valid, error_message)
        """
        
        # App name validation - strict lowercase alphanumeric with hyphens
        if not re.match(r'^[a-z0-9-]{3,50}$', app_name):
            return (False, "Invalid app name: must be 3-50 lowercase alphanumeric characters with hyphens only")
        
        # Check app name uniqueness
        spec_file = f"{self.output_dir}/{app_name}.json"
        if os.path.exists(spec_file):
            return (False, f"App name '{app_name}' already exists in registry")
        
        # Runtime type validation - strict enum
        if runtime_type not in ['backend', 'frontend', 'fullstack']:
            return (False, f"Invalid runtime type '{runtime_type}': must be 'backend', 'frontend', or 'fullstack'")
        
        # URL protocol validation
        if not (repo_url.startswith('http://') or repo_url.startswith('https://')):
            return (False, "Invalid URL: must start with http:// or https://")
        
        # URL length check
        if len(repo_url) > 500:
            return (False, "Invalid URL: exceeds maximum length of 500 characters")
        
        # URL safety check - prevent file:// and local paths
        if repo_url.startswith('file://'):
            return (False, "Invalid URL: file:// protocol not allowed")
        
        # Check for shell injection patterns
        unsafe_patterns = ['../', '/etc/', '/var/', 'rm ', 'del ', ';', '&&', '|', '`', '$(']
        for pattern in unsafe_patterns:
            if pattern in repo_url:
                return (False, f"Invalid URL: contains unsafe pattern '{pattern}'")

        # Structured URL validation for GitHub URL or website URL
        parsed = urlparse(repo_url)
        if not parsed.netloc:
            return (False, "Invalid URL: hostname is required")

        url_type = self._classify_url_type(repo_url)
        if url_type == 'github':
            if not self._is_valid_github_url(parsed):
                return (False, "Invalid GitHub URL: expected https://github.com/<owner>/<repo>")
        else:
            if not self._is_valid_website_url(parsed):
                return (False, "Invalid website URL: must be a valid public http(s) URL")
        
        return (True, None)

    def _classify_url_type(self, source_url: str) -> str:
        """Classify source URL as github or website."""
        parsed = urlparse(source_url)
        host = parsed.netloc.lower()
        if host == 'github.com' or host.endswith('.github.com'):
            return 'github'
        return 'website'

    def _is_valid_github_url(self, parsed_url) -> bool:
        """Validate GitHub repository URL format."""
        host = parsed_url.netloc.lower()
        if host != 'github.com':
            return False

        path = parsed_url.path.strip('/')
        if not path:
            return False

        segments = [segment for segment in path.split('/') if segment]
        if len(segments) < 2:
            return False

        owner = segments[0]
        repo = segments[1].removesuffix('.git')

        owner_ok = re.match(r'^[A-Za-z0-9_.-]+$', owner) is not None
        repo_ok = re.match(r'^[A-Za-z0-9_.-]+$', repo) is not None
        return owner_ok and repo_ok

    def _is_valid_website_url(self, parsed_url) -> bool:
        """Validate generic website URL format."""
        if parsed_url.scheme not in ('http', 'https'):
            return False

        host = parsed_url.netloc.lower()
        if not host:
            return False

        if host in ('localhost', '127.0.0.1'):
            return False

        # Require at least one dot in host for public website URLs
        return '.' in host

    def _extract_service_metadata(self, source_url: str, app_name: str, runtime_type: str) -> Dict[str, Any]:
        """Extract deterministic service metadata from URL and input fields."""
        parsed = urlparse(source_url)
        source_type = self._classify_url_type(source_url)

        metadata = {
            'source_type': source_type,
            'source_host': parsed.netloc.lower(),
            'source_path': parsed.path or '/',
            'service_name': app_name,
            'runtime_type': runtime_type,
            'detected_at': datetime.utcnow().isoformat() + 'Z'
        }

        if source_type == 'github':
            segments = [segment for segment in parsed.path.strip('/').split('/') if segment]
            owner = segments[0] if len(segments) > 0 else None
            repository = segments[1].removesuffix('.git') if len(segments) > 1 else None
            metadata.update({
                'provider': 'github',
                'owner': owner,
                'repository': repository,
                'repo_https_url': f"https://github.com/{owner}/{repository}" if owner and repository else source_url
            })
        else:
            metadata.update({
                'provider': 'website',
                'domain': parsed.netloc.lower(),
                'base_url': f"{parsed.scheme}://{parsed.netloc}"
            })

        return metadata
    
    def _generate_spec(self, repo_url, app_name, runtime_type):
        """Generate app_spec.json from input"""
        
        defaults = {
            'backend': {
                'build_command': 'pip install -r requirements.txt',
                'start_command': 'python app.py',
                'health_endpoint': '/health',
                'port': 5000
            },
            'frontend': {
                'build_command': 'npm install && npm run build',
                'start_command': 'npm start',
                'health_endpoint': '/index.html',
                'port': 3000
            },
            'fullstack': {
                'build_command': 'npm install && pip install -r requirements.txt',
                'start_command': 'npm run start:prod',
                'health_endpoint': '/api/health',
                'port': 8080
            }
        }
        
        config = defaults[runtime_type]
        service_metadata = self._extract_service_metadata(repo_url, app_name, runtime_type)
        
        return {
            "spec_version": "1.0",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "name": app_name,
            "type": runtime_type,
            "repo_path_or_url": repo_url,
            "source_type": service_metadata['source_type'],
            "build_command": config['build_command'],
            "start_command": config['start_command'],
            "health_endpoint": config['health_endpoint'],
            "environments": ["dev", "stage", "prod"],
            "port": config['port'],
            "resources": {
                "cpu": "0.5",
                "memory": "512Mi"
            },
            "scaling": {
                "min_replicas": 1,
                "max_replicas": 3,
                "target_cpu_percent": 70
            },
            "service_metadata": service_metadata
        }
    
    def _log_proof(self, event_type, data: Dict[str, Any]):
        """Log proof event if proof logging is enabled"""
        if not self.use_proof_logging or event_type is None:
            return
        
        try:
            self.proof_logger(event_type, data)
        except Exception:
            pass  # Silent fail if proof logging unavailable
    

    def _trigger_deployment(self, app_name: str, spec_file: str):
        """Trigger deployment for onboarded app"""

        # Log deployment trigger
        self._log_proof(self.ProofEvents.DEPLOYMENT_TRIGGERED if self.use_proof_logging else None, {
            'app_name': app_name,
            'spec_file': spec_file,
            'trigger_source': 'onboarding_entry'
        })

        try:
            # Import orchestrator
            from orchestrator.app_orchestrator import AppOrchestrator

            orchestrator = AppOrchestrator()

            print(f"🚀 Calling orchestrator.deploy_app({app_name})")

            result = orchestrator.deploy_app(app_name)

            if result.get("success"):
                print(f"✅ Deployment successful: {app_name}")
            else:
                print(f"❌ Deployment failed: {result}")

        except Exception as e:
            print(f"❌ Deployment trigger error: {e}")

    
    def _log(self, status: str, input_data: Dict[str, Any], result: str):
        """Log acceptance/rejection"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "input": input_data,
            "result": result
        }
        
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        
        # Color-coded output
        status_symbol = "✅" if status == "ACCEPTED" else "❌"
        print(f"{status_symbol} [{status}] {result}")

def cli_interface():
    """Command line interface"""
    print("=== App Onboarding Entry ===")
    
    repo_url = input("GitHub or Website URL: ").strip()
    app_name = input("App name: ").strip()
    runtime_type = input("Runtime type (backend/frontend/fullstack): ").strip()
    
    onboarder = OnboardingEntry()
    success = onboarder.process(repo_url, app_name, runtime_type)
    
    if success:
        print(f"App spec generated: apps/registry/{app_name}.json")
    
    return success

def json_interface(input_file):
    """JSON file interface"""
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    onboarder = OnboardingEntry()
    source_url = data.get('repo_url') or data.get('website_url') or data.get('url')
    return onboarder.process(
        source_url,
        data['app_name'], 
        data['runtime_type']
    )

if __name__ == "__main__":
    if len(sys.argv) > 1:
        success = json_interface(sys.argv[1])
    else:
        success = cli_interface()
    
    sys.exit(0 if success else 1)

def process_onboarding_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process onboarding request from API
    
    Args:
        request_data: Dict with keys: app_name, runtime, and one of repo_url/website_url/url
    
    Returns:
        Dict with keys: success, spec_file, message
    """
    onboarder = OnboardingEntry()
    
    app_name = request_data.get('app_name')
    repo_url = request_data.get('repo_url') or request_data.get('website_url') or request_data.get('url')
    runtime = request_data.get('runtime')
    
    # Validate required fields
    if not all([app_name, repo_url, runtime]):
        return {
            'success': False,
            'message': 'Missing required fields: app_name, runtime, and one of repo_url/website_url/url',
            'spec_file': None
        }
    
    # Process onboarding
    success = onboarder.process(repo_url, app_name, runtime)
    
    if success:
        spec_file = f"{onboarder.output_dir}/{app_name}.json"
        return {
            'success': True,
            'spec_file': spec_file,
            'message': f'Successfully onboarded {app_name}'
        }
    else:
        return {
            'success': False,
            'spec_file': None,
            'message': onboarder.last_error or 'Onboarding validation failed'
        }
