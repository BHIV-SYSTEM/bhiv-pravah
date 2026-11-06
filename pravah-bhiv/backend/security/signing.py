#!/usr/bin/env python3
"""SSPL Phase III - Payload Signing and Verification"""
import hashlib
import hmac
import json
import os
import time
from typing import Any

MAX_TRACE_AGE_SECONDS = 300
MAX_SERVICE_REQUEST_AGE_SECONDS = 300

def make_canonical(obj: Any) -> Any:
    from typing import Any as TypAny
    if isinstance(obj, dict):
        return {k: make_canonical(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, (list, tuple)):
        return [make_canonical(x) for x in obj]
    elif isinstance(obj, set):
        return [make_canonical(x) for x in sorted(list(obj), key=str)]
    elif hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        return make_canonical(obj.model_dump(mode="json"))
    elif hasattr(obj, "__dict__"):
        return make_canonical(obj.__dict__)
    return obj

def canonical_serialize(obj: Any) -> str:
    return json.dumps(make_canonical(obj), separators=(',', ':'), default=str)

from typing import Any

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

class PayloadSigner:
    """Signs and verifies payloads for SSPL Phase III compliance."""
    
    def __init__(self, secret_key: str | None = None):
        raw_env = os.getenv('ENVIRONMENT')
        norm_env, is_enforced = _normalize_and_validate_environment(raw_env)

        resolved_secret = secret_key if secret_key is not None else os.getenv('SSPL_SECRET_KEY')

        if is_enforced:
            if _is_placeholder_or_fallback(resolved_secret):
                if norm_env == 'prod':
                    raise ValueError('SSPL_SECRET_KEY must be set in production (cannot be empty, default fallback, or placeholder)')
                else:
                    raise ValueError('SSPL_SECRET_KEY must be set in staging (cannot be empty, default fallback, or placeholder)')
        else:
            if not resolved_secret or not resolved_secret.strip():
                resolved_secret = 'default-secret-key-change-in-prod'

        if resolved_secret is None:
            resolved_secret = 'default-secret-key-change-in-prod'

        self.secret_key = resolved_secret.strip()
    
    def sign_payload(self, payload_dict: dict) -> dict:
        """Sign payload and return with signature field."""
        # Create canonical string from payload
        canonical = canonical_serialize(payload_dict)
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.secret_key.encode(),
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Add signature to payload
        signed_payload = payload_dict.copy()
        signed_payload['signature'] = signature
        signed_payload['signature_algorithm'] = 'HMAC-SHA256'
        
        return signed_payload
    
    def verify_payload(self, payload_dict: dict, signature: str | None = None) -> bool:
        """Verify payload signature."""
        target_sig: Any = signature if signature is not None else payload_dict.get('signature')
        
        if not target_sig or not isinstance(target_sig, str):
            return False
        
        # Remove signature fields for verification
        payload_copy = payload_dict.copy()
        payload_copy.pop('signature', None)
        payload_copy.pop('signature_algorithm', None)
        
        # Recreate canonical string
        canonical = canonical_serialize(payload_copy)
        
        # Generate expected signature
        expected_signature = hmac.new(
            self.secret_key.encode(),
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison
        return hmac.compare_digest(target_sig, expected_signature)

# Global signer instance
_signer = None

def get_signer() -> PayloadSigner:
    """Get or create global signer instance."""
    global _signer
    if _signer is None:
        _signer = PayloadSigner()
    return _signer

def sign_payload(payload_dict: dict) -> dict:
    """Convenience function to sign payload."""
    return get_signer().sign_payload(payload_dict)

def verify_payload(payload_dict: dict, signature: str | None = None) -> bool:
    """Convenience function to verify payload."""
    return get_signer().verify_payload(payload_dict, signature)


def generate_body_hash(payload_dict: dict) -> str:
    canonical = canonical_serialize(payload_dict)

    return hashlib.sha256(
        canonical.encode()
    ).hexdigest()


def build_trace_payload(
    trace_id: str,
    timestamp: str,
    body_hash: str
) -> str:
    return f"{trace_id}:{timestamp}:{body_hash}"


def sign_trace(
    trace_id: str,
    timestamp: str,
    payload_dict: dict
) -> str:

    signer = get_signer()

    body_hash = generate_body_hash(payload_dict)

    payload = build_trace_payload(
        trace_id,
        timestamp,
        body_hash
    )

    return hmac.new(
        signer.secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_trace_signature(
    trace_id: str,
    timestamp: str,
    signature: str,
    payload_dict: dict
) -> bool:

    if not trace_id:
        return False

    if not timestamp:
        return False

    if not signature:
        return False

    try:
        request_time = int(timestamp)
    except Exception:
        return False

    now = int(time.time())

    if abs(now - request_time) > MAX_TRACE_AGE_SECONDS:
        return False

    expected_signature = sign_trace(
        trace_id,
        timestamp,
        payload_dict
    )

    return hmac.compare_digest(
        signature,
        expected_signature
    )


def build_service_payload(
    service_id: str,
    timestamp: str,
    nonce: str,
    body_hash: str
) -> str:
    return (
        f"{service_id}:"
        f"{timestamp}:"
        f"{nonce}:"
        f"{body_hash}"
    )


def sign_service_request(
    service_id: str,
    timestamp: str,
    nonce: str,
    payload_dict: dict
) -> str:

    signer = get_signer()

    body_hash = generate_body_hash(
        payload_dict
    )

    payload = build_service_payload(
        service_id,
        timestamp,
        nonce,
        body_hash
    )

    return hmac.new(
        signer.secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_service_request(
    service_id: str,
    timestamp: str,
    nonce: str,
    signature: str,
    payload_dict: dict
) -> bool:

    if not service_id:
        return False

    if not timestamp:
        return False

    if not nonce:
        return False

    if not signature:
        return False

    try:
        request_time = int(timestamp)
    except Exception:
        return False

    now = int(time.time())

    if abs(now - request_time) > MAX_SERVICE_REQUEST_AGE_SECONDS:
        return False

    expected_signature = sign_service_request(
        service_id,
        timestamp,
        nonce,
        payload_dict
    )

    return hmac.compare_digest(
        signature,
        expected_signature
    )