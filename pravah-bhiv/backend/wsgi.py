"""
Render-Safe Entry Point for Agent API
Ensures Flask server starts before agent loop initialization.
"""

import os
import sys

# Add project root and control_plane directory to path in correct priority order
root_dir = os.path.abspath(os.path.dirname(__file__))
control_plane_dir = os.path.join(root_dir, 'control_plane')

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if control_plane_dir not in sys.path:
    sys.path.append(control_plane_dir)


def load_environment_config(base_dir: str = None) -> str:
    """
    Safely resolves and loads the appropriate environment file based on ENVIRONMENT.
    Defaults to 'dev' for local development.
    Preserves externally injected environment variables (override=False).
    Explicitly rejects invalid environment names.
    """
    if base_dir is None:
        base_dir = os.path.abspath(os.path.dirname(__file__))

    raw_env = os.getenv("ENVIRONMENT")
    if raw_env is None or not raw_env.strip():
        raw_env = "dev"
    else:
        raw_env = raw_env.strip()

    valid_envs = {
        "dev": "dev",
        "development": "dev",
        "stage": "stage",
        "staging": "stage",
        "prod": "prod",
        "production": "prod",
    }
    env_lower = raw_env.lower()
    if env_lower not in valid_envs:
        raise ValueError(
            f"Invalid ENVIRONMENT '{raw_env}'. Must be one of: dev, stage, prod (or development, staging, production)."
        )

    normalized_env = valid_envs[env_lower]
    os.environ["ENVIRONMENT"] = normalized_env

    env_path = os.path.join(base_dir, 'environments', f'{normalized_env}.env')
    if os.path.exists(env_path):
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path, override=False)
        except ImportError:
            pass
    return normalized_env


# Initialize environment before importing application modules
load_environment_config(root_dir)

# Import the Flask app (this will initialize the agent in background)
# Wrapped to support both runtime execution (gunicorn wsgi:app) and test/tooling imports
try:
    from api.agent_api import app
except Exception:
    app = None

# Gunicorn will import this module and use the 'app' object
# The agent thread starts automatically when agent_api is imported

if __name__ == '__main__':
    # This block only runs for local development
    if app is None:
        raise RuntimeError("Failed to initialize Flask app for wsgi server.")
    port = int(os.getenv('CONTROL_PLANE_PORT', os.getenv('PORT', 7000)))
    print(f"Starting Agent API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
