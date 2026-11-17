#!/usr/bin/env python3
"""App Onboarding Tool - Validates and registers applications"""
import json
import yaml
import os
import re
from typing import Dict, Any, List

class AppOnboarder:
    """Validates and onboards applications to the registry."""
    
    REQUIRED_FIELDS = [
        'name', 'type', 'repo_path_or_url', 
        'build_command', 'start_command', 
        'health_endpoint', 'environments'
    ]
    
    VALID_TYPES = ['backend', 'frontend', 'fullstack']
    VALID_ENVIRONMENTS = ['dev', 'stage', 'prod']
    
    def __init__(self, registry_path='apps/registry'):
        self.registry_path = registry_path
        os.makedirs(registry_path, exist_ok=True)
    
    def load_spec(self, spec_file: str) -> Dict[str, Any]:
        """Load app spec from JSON or YAML file."""
        with open(spec_file, 'r') as f:
            if spec_file.endswith('.json'):
                return json.load(f)
            elif spec_file.endswith(('.yaml', '.yml')):
                return yaml.safe_load(f)
            else:
                raise ValueError("Spec file must be .json or .yaml")
    
    def validate_spec(self, spec: Dict[str, Any]) -> List[str]:
        """Validate app specification and return list of errors."""
        errors = []
        
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in spec:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return errors
        
        # Validate name
        if not re.match(r'^[a-zA-Z0-9_-]{3,50}$', spec['name']):
            errors.append("name must be 3-50 alphanumeric characters with hyphens/underscores")
        
        # Validate type
        if spec['type'] not in self.VALID_TYPES:
            errors.append(f"type must be one of: {', '.join(self.VALID_TYPES)}")
        
        # Validate repo_path_or_url
        if not spec['repo_path_or_url']:
            errors.append("repo_path_or_url cannot be empty")
        
        # Validate commands
        if not spec['build_command'].strip():
            errors.append("build_command cannot be empty")
        if not spec['start_command'].strip():
            errors.append("start_command cannot be empty")
        
        # Validate health_endpoint
        if not spec['health_endpoint'].startswith('/'):
            errors.append("health_endpoint must start with /")
        
        # Validate environments
        if not isinstance(spec['environments'], list) or not spec['environments']:
            errors.append("environments must be a non-empty array")
        else:
            invalid_envs = [e for e in spec['environments'] if e not in self.VALID_ENVIRONMENTS]
            if invalid_envs:
                errors.append(f"Invalid environments: {', '.join(invalid_envs)}")
        
        return errors
    
    def normalize_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize spec with defaults and metadata."""
        normalized = spec.copy()
        
        # Add defaults
        normalized.setdefault('port', 8080)
        normalized.setdefault('resources', {'cpu': '0.5', 'memory': '512Mi'})
        normalized.setdefault('scaling', {
            'min_replicas': 1,
            'max_replicas': 3,
            'target_cpu_percent': 70
        })
        
        # Add metadata
        normalized['registry_version'] = '1.0'
        normalized['onboarded_at'] = __import__('datetime').datetime.now().isoformat()
        
        return normalized
    
    def save_to_registry(self, spec: Dict[str, Any]) -> str:
        """Save normalized spec to registry."""
        app_name = spec['name']
        registry_file = os.path.join(self.registry_path, f"{app_name}.json")
        
        with open(registry_file, 'w') as f:
            json.dump(spec, f, indent=2)
        
        return registry_file
    
    def onboard(self, spec_file: str) -> Dict[str, Any]:
        """Complete onboarding process."""
        print(f"🚀 Onboarding app from: {spec_file}")
        
        # Load spec
        try:
            spec = self.load_spec(spec_file)
            print(f"✅ Loaded spec for: {spec.get('name', 'unknown')}")
        except Exception as e:
            return {'success': False, 'error': f"Failed to load spec: {e}"}
        
        # Validate spec
        errors = self.validate_spec(spec)
        if errors:
            print("❌ Validation failed:")
            for error in errors:
                print(f"   - {error}")
            return {'success': False, 'errors': errors}
        
        print("✅ Validation passed")
        
        # Normalize spec
        normalized_spec = self.normalize_spec(spec)
        print("✅ Spec normalized")
        
        # Save to registry
        try:
            registry_file = self.save_to_registry(normalized_spec)
            print(f"✅ Saved to registry: {registry_file}")
            
            return {
                'success': True,
                'app_name': normalized_spec['name'],
                'registry_file': registry_file,
                'spec': normalized_spec
            }
        except Exception as e:
            return {'success': False, 'error': f"Failed to save to registry: {e}"}

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Onboard application to registry")
    parser.add_argument("spec_file", help="Path to app_spec.json or app_spec.yaml")
    parser.add_argument("--registry", default="apps/registry", help="Registry directory")
    
    args = parser.parse_args()
    
    onboarder = AppOnboarder(args.registry)
    result = onboarder.onboard(args.spec_file)
    
    if result['success']:
        print(f"\n🎉 Successfully onboarded: {result['app_name']}")
        exit(0)
    else:
        print(f"\n❌ Onboarding failed")
        exit(1)