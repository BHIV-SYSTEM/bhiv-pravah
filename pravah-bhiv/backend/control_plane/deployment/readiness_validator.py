"""Phase 5 readiness validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from control_plane.persistence.replay_index import ReplayIndex

from .deployment_proof import DeploymentProofPacket
from .startup_validator import DeploymentPaths, StartupValidator


@dataclass(frozen=True)
class ReadinessValidationResult:
    ready: bool
    status: str
    readiness: Dict[str, bool]
    failures: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class ReadinessValidator:
    """Readiness means the deployment can safely accept traffic."""

    def __init__(self, paths: DeploymentPaths | None = None, proof_packet: DeploymentProofPacket | None = None):
        self.paths = paths or DeploymentPaths()
        self.proof_packet = proof_packet or DeploymentProofPacket()
        self.startup_validator = StartupValidator(paths=self.paths, proof_packet=self.proof_packet)

    def validate(self) -> ReadinessValidationResult:
        readiness = {
            "phase1_signed_lineage": self.startup_validator.append_only_log_exists() and self.startup_validator.replay_index_exists(),
            "phase2_policy_engine": self.startup_validator.policy_engine_loaded(),
            "phase3_persistence": self.startup_validator.snapshot_directory_exists(),
            "phase4_semantic_guard": self.startup_validator.semantic_guard_loaded(),
            "replay_index_loaded": self._replay_index_loaded(),
        }
        failures = [name for name, passed in readiness.items() if not passed]
        ready = not failures
        status = "READY" if ready else "NOT READY"

        self.proof_packet.record(
            "readiness",
            "readiness_validation",
            status=status,
            readiness=readiness,
            failures=failures,
        )

        return ReadinessValidationResult(
            ready=ready,
            status=status,
            readiness=readiness,
            failures=failures,
            details={
                "append_only_log_path": str(self.paths.append_only_log_path),
                "replay_index_path": str(self.paths.replay_index_path),
            },
        )

    def _replay_index_loaded(self) -> bool:
        try:
            index = ReplayIndex(index_path=str(self.paths.replay_index_path))
            _ = index.get_all_executions()
            return True
        except Exception:
            return False