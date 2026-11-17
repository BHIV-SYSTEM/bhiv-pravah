#!/usr/bin/env python3
"""Production Safety Guards - Block risky actions in prod environment"""

# Actions that are NEVER allowed in any environment (global safety)
GLOBALLY_BLOCKED_ACTIONS = {
    'delete_production_data',
    'modify_user_accounts', 
    'change_security_settings',
    'access_external_systems',
    'modify_system_files',
    'execute_shell_commands',
    'drop_database',
    'delete_backups',
    'format_drives'
}

# Actions blocked in production environment
PROD_BLOCKED_ACTIONS = {
    'scale_up',
    'scale_down', 
    'restore_previous_version',
    'adjust_thresholds'
}

# Only allow safe actions in prod
PROD_ALLOWED_ACTIONS = {
    'noop',
    'restart',
    'retry_deployment'
}

class ProductionSafetyError(Exception):
    """Raised when attempting risky action in production."""
    pass

def validate_prod_action(action: str, environment: str) -> bool:
    """Validate if action is safe for production environment.
    
    Args:
        action: Action to validate
        environment: Target environment (dev/stage/prod)
        
    Returns:
        True if action is allowed
        
    Raises:
        ProductionSafetyError: If action is blocked
    """
    # Global safety check - these actions are NEVER allowed in ANY environment
    if action in GLOBALLY_BLOCKED_ACTIONS:
        raise ProductionSafetyError(
            f"Action '{action}' is globally blocked for safety. "
            f"This action is never allowed in any environment."
        )
    
    # Production-specific checks
    if environment == 'prod':
        if action in PROD_BLOCKED_ACTIONS:
            raise ProductionSafetyError(
                f"Action '{action}' is blocked in production environment. "
                f"Allowed actions: {sorted(PROD_ALLOWED_ACTIONS)}"
            )
        
        if action not in PROD_ALLOWED_ACTIONS:
            raise ProductionSafetyError(
                f"Action '{action}' is not in production whitelist. "
                f"Allowed actions: {sorted(PROD_ALLOWED_ACTIONS)}"
            )
    
    return True

def is_action_safe_for_prod(action: str) -> bool:
    """Check if action is safe for production without raising exception."""
    return action in PROD_ALLOWED_ACTIONS

def is_demo_mode_safe(action: str, source: str = None) -> tuple[bool, str]:
    """
    Validate action for DEMO_MODE execution gate.
    
    Args:
        action: Action to validate
        source: Source identifier of the action
        
    Returns:
        Tuple of (is_safe, reason) - safe actions return (True, ""), 
        unsafe actions return (False, refusal_reason)
    """
    try:
        from demo_mode_config import (
            is_demo_mode_active,
            is_action_allowed,
            is_action_blocked,
            validate_action_source,
            get_refusal_reason
        )
        
        if not is_demo_mode_active():
            return (True, "")  # Demo mode not active
        
        # Check if action is explicitly blocked
        if is_action_blocked(action):
            return (False, get_refusal_reason(action, source))
        
        # Check if action is on allowlist
        if not is_action_allowed(action):
            return (False, get_refusal_reason(action, source))
        
        # Validate source if provided
        if source and not validate_action_source(source):
            return (False, get_refusal_reason(action, source))
        
        return (True, "")
        
    except ImportError:
        # Demo mode config not available, allow action
        return (True, "")