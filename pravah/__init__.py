"""
PRAVAH Package Interface
"""

import os
import sys
from pathlib import Path

# Ensure control_plane and contracts can be resolved
_current_dir = Path(__file__).resolve().parent
_backend_candidates = [
    _current_dir.parent / "pravah-bhiv" / "backend",
    _current_dir.parent / "backend",
    _current_dir.parent,
]
for _candidate in _backend_candidates:
    if (_candidate / "control_plane").exists() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from pravah.schema_validator import (
    InboundSignalV1,
    OutboundEventV1,
    SchemaValidatorV1,
    SchemaValidationError,
    ValidationErrorCode,
    ValidationResult,
)
from pravah.replay_ledger import (
    ReplayLedger,
    ReplayLedgerError,
    ReplayTamperingError,
    compute_canonical_hash,
    canonical_json_dump,
)
from pravah.stream_processor import (
    StreamProcessor,
    StreamProcessorError,
    InvalidStateTransitionError,
    TerminalStateLockedError,
)

__all__ = [
    "InboundSignalV1",
    "OutboundEventV1",
    "SchemaValidatorV1",
    "SchemaValidationError",
    "ValidationErrorCode",
    "ValidationResult",
    "ReplayLedger",
    "ReplayLedgerError",
    "ReplayTamperingError",
    "compute_canonical_hash",
    "canonical_json_dump",
    "StreamProcessor",
    "StreamProcessorError",
    "InvalidStateTransitionError",
    "TerminalStateLockedError",
]
