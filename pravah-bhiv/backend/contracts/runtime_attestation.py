from __future__ import annotations

import hashlib
import json
import os
import platform
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_payload(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _hash_file(path: str) -> Optional[str]:
    try:
        p = Path(path)
        if not p.exists():
            return None
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


class RuntimeAttestation(BaseModel):
    runtime_id: str
    runtime_version: str
    runtime_hash: str
    environment_hash: str
    manifest_hash: str


def compute_manifest_hash(manifest: Dict[str, Any]) -> str:
    return _hash_payload(manifest)


def compute_environment_hash(environment: Dict[str, Any]) -> str:
    return _hash_payload(environment)


def compute_runtime_attestation(
    *,
    manifest: Optional[Dict[str, Any]] = None,
    environment: Optional[Dict[str, Any]] = None,
    runtime_version: Optional[str] = None,
    executor_binary_path: Optional[str] = None,
) -> RuntimeAttestation:
    # Build deterministic defaults
    if manifest is None:
        repo_root = Path(__file__).resolve().parents[1]
        req_file = repo_root / "requirements.txt"
        reqs = ""
        if req_file.exists():
            try:
                reqs = req_file.read_text(encoding="utf-8")
            except Exception:
                reqs = ""
        manifest = {
            "python_version": platform.python_version(),
            "requirements_txt": reqs,
        }

    if environment is None:
        # Capture a small deterministic subset of environment variables (sorted)
        env = {k: os.environ.get(k, "") for k in sorted(os.environ) if k.startswith(("APP_", "ENV_", "RUNTIME_"))}
        environment = env

    if runtime_version is None:
        runtime_version = platform.python_version()

    executor_hash = None
    if executor_binary_path:
        executor_hash = _hash_file(executor_binary_path)
    else:
        # best-effort fallback to Python executable
        try:
            executor_hash = _hash_file(os.sys.executable)
        except Exception:
            executor_hash = None

    manifest_hash = compute_manifest_hash(manifest)
    environment_hash = compute_environment_hash(environment)

    runtime_payload = {
        "runtime_version": runtime_version,
        "manifest_hash": manifest_hash,
        "environment_hash": environment_hash,
        "executor_binary_hash": executor_hash,
    }

    runtime_hash = _hash_payload(runtime_payload)

    # Deterministic runtime id derived from runtime_hash
    runtime_id = str(uuid.uuid5(uuid.NAMESPACE_OID, runtime_hash))

    return RuntimeAttestation(
        runtime_id=runtime_id,
        runtime_version=runtime_version,
        runtime_hash=runtime_hash,
        environment_hash=environment_hash,
        manifest_hash=manifest_hash,
    )


def verify_runtime_attestation(attestation: Dict[str, Any]) -> tuple[bool, str]:
    """Basic deterministic verification of a runtime attestation payload.

    This function performs structural checks and recomputes the runtime_hash
    from the declared manifest_hash/environment_hash/executor_binary_hash
    fields when present. It is a software-rooted, best-effort verifier.
    """
    try:
        declared_runtime_hash = attestation.get("runtime_hash")
        runtime_version = attestation.get("runtime_version")
        manifest_hash = attestation.get("manifest_hash")
        environment_hash = attestation.get("environment_hash")

        payload = {
            "runtime_version": runtime_version,
            "manifest_hash": manifest_hash,
            "environment_hash": environment_hash,
            "executor_binary_hash": attestation.get("executor_binary_hash"),
        }
        computed = _hash_payload(payload)
        if declared_runtime_hash != computed:
            return False, "runtime_hash_mismatch"

        # Basic field presence checks
        if not attestation.get("runtime_id") or not runtime_version:
            return False, "missing_fields"

        return True, "ok"
    except Exception as e:
        return False, str(e)
