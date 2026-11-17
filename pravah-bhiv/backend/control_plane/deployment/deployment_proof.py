"""Deployment verification packet writer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from .json_logger import StructuredJsonLogger


PACKET_FILE_NAMES = {
    "startup": "startup_validation.log",
    "readiness": "readiness_validation.log",
    "recovery": "recovery_validation.log",
    "hash": "hash_verification.log",
    "replay": "replay_reconstruction.log",
}


@dataclass
class DeploymentProofPacket:
    packet_dir: Path | str = Path("deployment_verification_packet")
    file_names: Dict[str, str] = field(default_factory=lambda: dict(PACKET_FILE_NAMES))

    def __post_init__(self) -> None:
        self.packet_dir = Path(self.packet_dir)
        self.packet_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        return self.packet_dir / self.file_names[key]

    def logger_for(self, key: str) -> StructuredJsonLogger:
        return StructuredJsonLogger(self.path_for(key))

    def record(self, key: str, event: str, **payload: Any) -> Dict[str, Any]:
        logger = self.logger_for(key)
        record = logger.emit(event, phase="phase5", **payload)
        return {
            "event": record.event,
            "timestamp": record.timestamp,
            **record.payload,
        }