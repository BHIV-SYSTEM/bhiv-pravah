"""Phase 5 startup validation."""

from __future__ import annotations

import importlib
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .deployment_proof import DeploymentProofPacket


@dataclass(frozen=True)
class DeploymentPaths:
    append_only_log_path: Path = Path("logs/control_plane/append_only_log.jsonl")
    replay_index_path: Path = Path("logs/control_plane/replay_index.json")
    snapshot_directory: Path = Path("logs/control_plane/snapshots")
    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_timeout_seconds: float = 1.0


@dataclass(frozen=True)
class StartupValidationResult:
    ready: bool
    status: str
    checks: Dict[str, bool]
    failures: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class StartupValidator:
    """Pre-admission validation for deployment startup."""

    def __init__(self, paths: DeploymentPaths | None = None, proof_packet: DeploymentProofPacket | None = None):
        self.paths = paths or DeploymentPaths()
        self.proof_packet = proof_packet or DeploymentProofPacket()

    def append_only_log_exists(self) -> bool:
        return Path(self.paths.append_only_log_path).exists()

    def replay_index_exists(self) -> bool:
        return Path(self.paths.replay_index_path).exists()

    def snapshot_directory_exists(self) -> bool:
        return Path(self.paths.snapshot_directory).exists() and Path(self.paths.snapshot_directory).is_dir()

    def redis_available(self) -> bool:
        try:
            with socket.create_connection((self.paths.redis_host, self.paths.redis_port), timeout=self.paths.redis_timeout_seconds):
                return True
        except OSError:
            return False

    def policy_engine_loaded(self) -> bool:
        try:
            module = importlib.import_module("control_plane.security.deterministic_policy_engine")
            return hasattr(module, "DeterministicPolicyEngine")
        except Exception:
            return False

    def semantic_guard_loaded(self) -> bool:
        try:
            module = importlib.import_module("control_plane.security.semantic_guard_engine")
            return hasattr(module, "get_semantic_guard")
        except Exception:
            return False

    def validate(self) -> StartupValidationResult:
        checks = {
            "append_only_log_exists": self.append_only_log_exists(),
            "replay_index_exists": self.replay_index_exists(),
            "snapshot_directory_exists": self.snapshot_directory_exists(),
            "redis_available": self.redis_available(),
            "policy_engine_loaded": self.policy_engine_loaded(),
            "semantic_guard_loaded": self.semantic_guard_loaded(),
        }
        failures = [name for name, passed in checks.items() if not passed]
        ready = not failures
        status = "READY" if ready else "SERVICE NOT READY"

        self.proof_packet.record(
            "startup",
            "startup_validation",
            status=status,
            checks=checks,
            failures=failures,
        )

        return StartupValidationResult(
            ready=ready,
            status=status,
            checks=checks,
            failures=failures,
            details={
                "append_only_log_path": str(self.paths.append_only_log_path),
                "replay_index_path": str(self.paths.replay_index_path),
                "snapshot_directory": str(self.paths.snapshot_directory),
                "redis_host": self.paths.redis_host,
                "redis_port": self.paths.redis_port,
            },
        )