from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_policy_hash(policy_definition: Dict[str, Any]) -> str:
    """Deterministic SHA256 over canonical JSON of the policy definition."""
    return hashlib.sha256(_canonical_json(policy_definition).encode('utf-8')).hexdigest()


class PolicySnapshot(dict):
    """Minimal policy snapshot object.

    Keys:
      - policy_id
      - policy_version
      - policy_hash
    """
    def __init__(self, policy_id: str, policy_version: str, policy_hash: str):
        super().__init__(policy_id=policy_id, policy_version=policy_version, policy_hash=policy_hash)
