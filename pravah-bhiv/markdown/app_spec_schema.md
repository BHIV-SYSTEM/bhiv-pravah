# App Specification Schema

Scope note:

- This document describes a full/superset app spec contract for onboarding and automation.
- Current multi-app listing logic primarily relies on `name`, `type`, `source_type`, and `health_endpoint` fields from registry JSON files.
- Additional fields in this document are recommended for richer deployment automation but may not be required by every runtime path.

## Overview
Unified app specification format aligned with Ritesh's RL interpreter requirements.

## Required Fields

### Core Metadata
- **name** (string, required): Application name (alphanumeric, hyphens, underscores)
- **type** (enum, required): Application type
  - `backend` - Backend API service
  - `frontend` - Frontend web application
  - `fullstack` - Combined backend + frontend

### Repository
- **repo_path_or_url** (string, required): Local path or Git repository URL
  - Local: `./apps/sample_backend`
  - Remote: `https://github.com/user/repo.git`

### Build & Deployment
- **build_command** (string, required): Command to build the application
  - Example: `pip install -r requirements.txt`
  - Example: `npm install && npm run build`
- **start_command** (string, required): Command to start the application
  - Example: `python app.py`
  - Example: `npm start`

### Health Monitoring
- **health_endpoint** (string, required): HTTP endpoint for health checks
  - Example: `/health`
  - Example: `/api/health`
  - Must return 200 OK when healthy

### Environment Configuration
- **environments** (array, required): Supported deployment environments
  - Values: `dev`, `stage`, `prod`
  - Each environment can have specific configurations

## Optional Fields

### Resource Specifications
- **resources** (object, optional):
  - `cpu`: CPU allocation (e.g., "0.5", "1.0")
  - `memory`: Memory allocation (e.g., "512Mi", "1Gi")

### Scaling Configuration
- **scaling** (object, optional):
  - `min_replicas`: Minimum number of instances
  - `max_replicas`: Maximum number of instances
  - `target_cpu_percent`: CPU threshold for auto-scaling

### Dependencies
- **dependencies** (array, optional): List of dependency files
  - Example: `["requirements.txt", "package.json"]`

### Port Configuration
- **port** (integer, optional): Application port (default: 8080)

## Example Specification

```json
{
  "name": "sample-backend",
  "type": "backend",
  "repo_path_or_url": "./apps/sample_backend",
  "build_command": "pip install -r requirements.txt",
  "start_command": "python app.py",
  "health_endpoint": "/health",
  "environments": ["dev", "stage", "prod"],
  "port": 5000,
  "resources": {
    "cpu": "0.5",
    "memory": "512Mi"
  },
  "scaling": {
    "min_replicas": 1,
    "max_replicas": 5,
    "target_cpu_percent": 70
  }
}
```

## Validation Rules

1. **name**: Must be unique, 3-50 characters, alphanumeric with hyphens/underscores
2. **type**: Must be one of: backend, frontend, fullstack
3. **repo_path_or_url**: Must be valid path or URL
4. **build_command**: Non-empty string
5. **start_command**: Non-empty string
6. **health_endpoint**: Must start with `/`
7. **environments**: Must contain at least one valid environment

## Integration with RL Interpreter

This schema is synchronized with Ritesh's RL interpreter for:
- **Deployment decisions**: Using `environments` and `scaling` fields
- **Health monitoring**: Using `health_endpoint` for status checks
- **Resource optimization**: Using `resources` for allocation decisions
- **Build automation**: Using `build_command` and `start_command` for CI/CD