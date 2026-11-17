#!/usr/bin/env python3
"""SSPL Phase III - Nonce Store for Replay Attack Prevention"""
import logging
import time
import json
import os
from typing import Set

logger = logging.getLogger("security.nonce_store")

class NonceStore:
    """Stores nonces to prevent replay attacks."""

    def __init__(self, store_file: str = 'security/nonce_store.json', ttl: int = 3600):
        self.store_file = store_file
        self.ttl = ttl  # Time-to-live in seconds
        self.nonces: Set[str] = set()
        self.nonce_timestamps = {}
        self._load_store()

    def _load_store(self):
        """Load nonces from file. Fails closed on corruption or read errors."""
        if os.path.exists(self.store_file):
            try:
                with open(self.store_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError("Store root must be a JSON object")
                    nonces = data.get('nonces')
                    timestamps = data.get('timestamps')
                    if not isinstance(nonces, list) or not isinstance(timestamps, dict):
                        raise ValueError("Store missing valid 'nonces' list or 'timestamps' dict")
                    self.nonces = set(nonces)
                    self.nonce_timestamps = dict(timestamps)
                    self._cleanup_expired()
            except Exception as exc:
                logger.critical("Nonce store corrupted or unreadable at '%s': %s", self.store_file, exc)
                raise RuntimeError(f"Nonce store unreadable or corrupted: {exc}") from exc

    def _save_store(self):
        """Save nonces to file atomically. Fails closed on write errors."""
        store_dir = os.path.dirname(self.store_file)
        if store_dir:
            os.makedirs(store_dir, exist_ok=True)
        temp_file = f"{self.store_file}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'nonces': list(self.nonces),
                    'timestamps': self.nonce_timestamps
                }, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, self.store_file)
        except Exception as exc:
            logger.critical("Failed to persist nonce store to '%s': %s", self.store_file, exc)
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            raise RuntimeError(f"Nonce persistence failed: {exc}") from exc

    def _cleanup_expired(self):
        """Remove expired nonces."""
        current_time = time.time()
        expired = [
            nonce for nonce, timestamp in self.nonce_timestamps.items()
            if current_time - timestamp > self.ttl
        ]
        for nonce in expired:
            self.nonces.discard(nonce)
            self.nonce_timestamps.pop(nonce, None)

    def check_and_store(self, nonce: str) -> bool:
        """
        Check if nonce is valid and store it. Returns True if valid (not seen before).
        Rolls back complete in-memory state and raises RuntimeError if persistence fails.
        """
        if not nonce:
            return False

        # Complete pre-operation snapshot to ensure exact rollback on save failure
        pre_nonces = set(self.nonces)
        pre_timestamps = dict(self.nonce_timestamps)

        self._cleanup_expired()

        if nonce in self.nonces:
            return False  # Replay attack detected

        # Store nonce
        self.nonces.add(nonce)
        self.nonce_timestamps[nonce] = time.time()
        try:
            self._save_store()
        except Exception:
            self.nonces = pre_nonces
            self.nonce_timestamps = pre_timestamps
            raise

        return True

    def is_valid(self, nonce: str) -> bool:
        """Check if nonce is valid without storing."""
        if not nonce:
            return False
        self._cleanup_expired()
        return nonce not in self.nonces

# Global nonce store instance
_nonce_store = None
_default_store_file = None

def get_nonce_store() -> NonceStore:
    """Get or create global nonce store."""
    global _nonce_store
    if _nonce_store is None:
        if _default_store_file is not None:
            _nonce_store = NonceStore(store_file=_default_store_file)
        else:
            _nonce_store = NonceStore()
    return _nonce_store

def check_nonce(nonce: str) -> bool:
    """Convenience function to check and store nonce."""
    return get_nonce_store().check_and_store(nonce)

def reset_nonce_store(store_file: str | None = None) -> None:
    """Reset global nonce store singleton (for testing)."""
    global _nonce_store, _default_store_file
    _nonce_store = None
    _default_store_file = store_file
