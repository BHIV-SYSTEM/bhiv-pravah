"""Healthcheck helper for replay validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .deployment_proof import DeploymentProofPacket
from .recovery_validator import RecoveryValidationResult, RecoveryValidator
from .startup_validator import DeploymentPaths


@dataclass(frozen=True)
class ReplayHealthcheckResult:
    healthy: bool
    status: str
    recovery: RecoveryValidationResult
    details: Dict[str, Any]


class ReplayHealthcheck:
    def __init__(self, paths: DeploymentPaths | None = None, proof_packet: DeploymentProofPacket | None = None):
        self.paths = paths or DeploymentPaths()
        self.proof_packet = proof_packet or DeploymentProofPacket()
        self.recovery_validator = RecoveryValidator(paths=self.paths, proof_packet=self.proof_packet)

    def check(self, execution_id: str, expected_state_hash: str | None = None) -> ReplayHealthcheckResult:
        recovery = self.recovery_validator.validate(execution_id, expected_state_hash=expected_state_hash)
        return ReplayHealthcheckResult(
            healthy=recovery.ready,
            status=recovery.status,
            recovery=recovery,
            details={"execution_id": execution_id},
        )