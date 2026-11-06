#!/usr/bin/env python3
"""JWT Token Authentication for Integration Endpoints"""
import jwt
import os
import time
from functools import wraps

KNOWN_DEV_FALLBACK_KEYS = {
    'default-jwt-secret-change-in-prod',
    'default-secret-key-change-in-prod',
    'pravah-sovereign-lineage-key',
    'dev-key',
    'change-me',
    'secret',
    'shakti-secret-key-change-in-prod',
    'default-secret-key',
}

def _is_placeholder_or_fallback(secret: str | None) -> bool:
    if secret is None or not secret.strip():
        return True
    s = secret.strip()
    if s in KNOWN_DEV_FALLBACK_KEYS:
        return True
    if s.startswith('##') and s.endswith('##'):
        return True
    lower = s.lower()
    if any(m in lower for m in ('change-in-prod', 'placeholder', 'will_be_injected', 'your-secret-here')):
        return True
    return False

def _normalize_and_validate_environment(env_str: str | None) -> tuple[str, bool]:
    if env_str is None or not env_str.strip():
        return 'dev', False
    raw = env_str.strip().lower()
    if raw in ('dev', 'development', 'local', 'test'):
        return 'dev', False
    elif raw in ('stage', 'staging'):
        return 'stage', True
    elif raw in ('prod', 'production'):
        return 'prod', True
    else:
        raise ValueError(
            f"Invalid or unsupported ENVIRONMENT '{env_str}'. Must be one of: dev, stage, prod (or development, staging, production)."
        )

class TokenAuth:
    """JWT token authentication."""
    
    def __init__(self, secret_key: str | None = None):
        raw_env = os.getenv('ENVIRONMENT')
        norm_env, is_enforced = _normalize_and_validate_environment(raw_env)

        resolved_key = secret_key if secret_key is not None else os.getenv('JWT_SECRET_KEY')

        if is_enforced:
            if _is_placeholder_or_fallback(resolved_key):
                if norm_env == 'prod':
                    raise ValueError('JWT_SECRET_KEY must be explicitly set to a secure, non-default secret in production')
                else:
                    raise ValueError('JWT_SECRET_KEY must be explicitly set to a secure, non-default secret in staging')
        else:
            if not resolved_key or not resolved_key.strip():
                resolved_key = 'default-jwt-secret-change-in-prod'

        if resolved_key is None:
            resolved_key = 'default-jwt-secret-change-in-prod'

        self.secret_key = resolved_key.strip()
        self.algorithm = 'HS256'
    
    def generate_token(self, user_id: str, expires_in: int = 3600) -> str:
        """Generate JWT token."""
        payload = {
            'user_id': user_id,
            'exp': time.time() + expires_in,
            'iat': time.time()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> dict:
        """Verify JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return {'valid': True, 'payload': payload}
        except jwt.ExpiredSignatureError:
            return {'valid': False, 'error': 'Token expired'}
        except jwt.InvalidTokenError:
            return {'valid': False, 'error': 'Invalid token'}
    
    def require_token(self, func):
        """Decorator to require token authentication."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check for token in environment or kwargs
            token = kwargs.get('token') or os.getenv('API_TOKEN')
            
            if not token:
                raise PermissionError('No authentication token provided')
            
            result = self.verify_token(token)
            if not result['valid']:
                raise PermissionError(f"Authentication failed: {result.get('error')}")
            
            return func(*args, **kwargs)
        return wrapper

# Global auth instance
_auth = None

def get_auth() -> TokenAuth:
    """Get or create global auth instance."""
    global _auth
    if _auth is None:
        _auth = TokenAuth()
    return _auth

def verify_token(token: str) -> bool:
    """Convenience function to verify token."""
    result = get_auth().verify_token(token)
    return result['valid']

def require_auth(func):
    """Decorator for requiring authentication."""
    return get_auth().require_token(func)
