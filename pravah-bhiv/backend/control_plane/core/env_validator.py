"""Environment configuration validator."""

import os

# Required environment variables
REQUIRED_VARS = {
    'ENVIRONMENT': str,
    'DEBUG': bool,
    'LOG_LEVEL': str,
    'DB_HOST': str,
    'DB_PORT': int,
    'REDIS_HOST': str,
    'REDIS_PORT': int,
    'DEPLOYMENT_TIMEOUT': int,
    'LATENCY_THRESHOLD_MS': int,
    'LOW_SCORE_THRESHOLD': int
}

# Valid values for specific variables
VALID_VALUES = {
    'ENVIRONMENT': ['dev', 'stage', 'prod'],
    'LOG_LEVEL': ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    'DEBUG': ['true', 'false']
}

def validate_env(env_name):
    """Validate environment configuration."""
    env_file = os.path.join("environments", f"{env_name}.env")
    
    # Check if env file exists
    if not os.path.exists(env_file):
        raise EnvironmentError(f"❌ Environment file missing: {env_file}")
    
    # Load environment variables manually
    env_vars = {}
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('export '):
                line = line[7:].strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            
            # Handle inline comments
            if ' #' in line:
                line = line.split(' #', 1)[0].strip()
                
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            # Prevent Errno 22 on invalid keys (empty, spaces, etc.)
            import re
            if not key or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                continue
                
            env_vars[key] = value
            os.environ[key] = value
    
    errors = []
    
    # Check required variables
    for var, var_type in REQUIRED_VARS.items():
        value = env_vars.get(var)
        
        if value is None:
            errors.append(f"Missing required variable: {var}")
            continue
        
        # Type validation
        if var_type == int:
            try:
                int(value)
            except ValueError:
                errors.append(f"{var} must be an integer, got: {value}")
        
        elif var_type == bool:
            if value.lower() not in ['true', 'false']:
                errors.append(f"{var} must be true/false, got: {value}")
        
        # Value validation
        if var in VALID_VALUES:
            if value not in VALID_VALUES[var]:
                errors.append(f"{var} must be one of {VALID_VALUES[var]}, got: {value}")
    
    # Check numeric ranges
    try:
        timeout = int(os.getenv('DEPLOYMENT_TIMEOUT', 0))
        if timeout < 10 or timeout > 300:
            errors.append("DEPLOYMENT_TIMEOUT must be between 10-300 seconds")
    except:
        pass
    
    if errors:
        error_msg = f"❌ Environment '{env_name}' validation failed:\n" + "\n".join(f"  • {e}" for e in errors)
        raise EnvironmentError(error_msg)
    
    print(f"Environment '{env_name}' validated successfully")
    return True

def get_env_config(env_name):
    """Get validated environment configuration."""
    validate_env(env_name)
    
    config = {}
    for var in REQUIRED_VARS:
        value = os.getenv(var)
        if REQUIRED_VARS[var] == int:
            config[var] = int(value)
        elif REQUIRED_VARS[var] == bool:
            config[var] = value.lower() == 'true'
        else:
            config[var] = value
    
    return config