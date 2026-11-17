"""
PRAVAH Replay Ledger
Append-only evidence ledger for deterministic replay, audit, and cryptographic verification.

Guarantees:
- Append-only immutability (never overwrites historical evidence)
- Monotonic sequence numbers per execution_id
- Cryptographic hash-chain linkage (SHA-256)
- Deterministic state reconstruction
- Integration with AppendOnlyLog and HashLineageVerifier
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from control_plane.persistence.append_only_log import (
    AppendOnlyLog,
    ExecutionEvent,
    HashChainBreak,
    OrderingViolation,
)
from control_plane.persistence.hash_lineage_verifier import (
    HashLineageVerifier,
    VerificationStatus,
)
from control_plane.persistence.replay_index import ReplayIndex


class ReplayLedgerError(Exception):
    """Base exception for Replay Ledger failures."""
    pass


class ReplayTamperingError(ReplayLedgerError):
    """Raised when ledger detects tampering or broken hash chains."""
    pass


def canonical_json_dump(data: Any) -> str:
    """Deterministic, canonical JSON serialization."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def compute_canonical_hash(data: Any) -> str:
    """Compute SHA-256 hash of canonically serialized object."""
    return hashlib.sha256(canonical_json_dump(data).encode("utf-8")).hexdigest()


class ReplayLedger:
    """
    Append-Only Cryptographic Replay Ledger.
    
    Provides high-level replay evidence management atop AppendOnlyLog.
    Guarantees no records can be silently mutated or deleted.
    """

    def __init__(
        self,
        log_path: str = "logs/control_plane/append_only_log.jsonl",
        index_path: str = "logs/control_plane/replay_index.json",
    ):
        self.log_path = Path(log_path)
        self.index_path = Path(index_path)
        self._lock = threading.RLock()
        
        # Underlying verified persistence components
        self._log = AppendOnlyLog(str(self.log_path))
        self._index = ReplayIndex(str(self.index_path))
        self._verifier = HashLineageVerifier()

    def record_event(
        self,
        execution_id: str,
        event_id: str,
        state: str,
        timestamp: Union[int, str],
        source: str,
        details: Dict[str, Any],
        previous_hash: Optional[str] = None,
    ) -> ExecutionEvent:
        """
        Record a new immutable event in the replay ledger.
        
        Strictly append-only. Validates hash chain continuity.
        """
        with self._lock:
            # Determine expected previous hash if not provided
            expected_prev = self.get_latest_event_hash(execution_id)
            if previous_hash is None:
                previous_hash = expected_prev
            elif previous_hash != expected_prev:
                raise ReplayTamperingError(
                    f"Hash chain break for {execution_id}: expected previous {expected_prev}, got {previous_hash}"
                )

            numeric_ts = int(timestamp) if isinstance(timestamp, (int, float)) else 0

            # Compute canonical event hash compatible with HashLineageVerifier
            event_content = {
                "execution_id": execution_id,
                "event_id": event_id,
                "state": state,
                "timestamp": numeric_ts,
                "source": source,
                "details": details,
            }
            event_hash = HashLineageVerifier._compute_event_hash(event_content)

            try:
                event = self._log.append(
                    execution_id=execution_id,
                    event_id=event_id,
                    state=state,
                    timestamp=numeric_ts,
                    event_hash=event_hash,
                    previous_hash=previous_hash,
                    source=source,
                    details=details,
                )
            except (HashChainBreak, OrderingViolation) as e:
                raise ReplayTamperingError(f"Ledger append rejected: {e}") from e

            # Update replay index
            events = self.get_events(execution_id)
            if events:
                self._index.update_execution(
                    execution_id=execution_id,
                    start_sequence=events[0].sequence,
                    end_sequence=events[-1].sequence,
                    event_count=len(events),
                    first_event_hash=events[0].event_hash,
                    last_event_hash=events[-1].event_hash,
                    last_timestamp=numeric_ts,
                    source_ids=[e.source for e in events],
                )

            return event

    def get_events(self, execution_id: str) -> List[ExecutionEvent]:
        """Retrieve all recorded events for execution_id in chronological sequence."""
        with self._lock:
            return self._log.get_execution_events(execution_id)

    def get_latest_event(self, execution_id: str) -> Optional[ExecutionEvent]:
        """Get the most recent event for execution_id."""
        with self._lock:
            return self._log.get_last_event(execution_id)

    def get_latest_event_hash(self, execution_id: str) -> str:
        """Return latest event hash or empty string for genesis."""
        with self._lock:
            latest = self.get_latest_event(execution_id)
            return latest.event_hash if latest else ""

    def compute_state_hash(self, execution_id: str) -> str:
        """
        Compute deterministic cumulative state hash across all events.
        
        State hash is SHA-256 concatenation of all event hashes in order.
        """
        with self._lock:
            events = self.get_events(execution_id)
            if not events:
                return hashlib.sha256(b"").hexdigest()
            combined = "".join(e.event_hash for e in events)
            return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def verify_replay(self, execution_id: str) -> Dict[str, Any]:
        """
        Verify cryptographic integrity of the execution event sequence.
        
        Guarantees:
        - Sequence numbers are strictly monotonic: 1, 2, ..., n
        - Hash chain is contiguous: event[i].previous_hash == event[i-1].event_hash
        - Lineage proofs and sequence hashes are valid
        """
        with self._lock:
            events = self.get_events(execution_id)
            if not events:
                return {
                    "is_valid": False,
                    "status": "NOT_FOUND",
                    "events_verified": 0,
                    "execution_id": execution_id,
                    "state_hash": hashlib.sha256(b"").hexdigest(),
                    "error": f"No events recorded for execution_id: {execution_id}",
                }

            events_dict = [asdict(e) for e in events]
            # Signature: verify_execution_lineage(self, events: List[Dict], execution_id: str)
            res = self._verifier.verify_execution_lineage(events_dict, execution_id)
            state_hash = self.compute_state_hash(execution_id)

            return {
                "is_valid": res.is_valid,
                "status": res.status.value,
                "events_verified": res.events_verified,
                "execution_id": execution_id,
                "state_hash": state_hash,
                "error_sequence": res.error_sequence,
                "error_detail": res.error_detail,
            }

    def is_tampered(self, execution_id: str) -> bool:
        """Return True if any event in the chain fails cryptographic verification."""
        v = self.verify_replay(execution_id)
        return not v["is_valid"]

    def reconstruct_state(self, execution_id: str) -> Dict[str, Any]:
        """
        Deterministically reconstruct current execution state from append-only events.
        """
        with self._lock:
            events = self.get_events(execution_id)
            if not events:
                raise ReplayLedgerError(f"No execution found for {execution_id}")

            v = self.verify_replay(execution_id)
            if not v["is_valid"]:
                raise ReplayTamperingError(f"Integrity check failed: {v.get('error_detail')}")

            history = [e.state for e in events]
            last_event = events[-1]

            return {
                "execution_id": execution_id,
                "current_state": last_event.state,
                "sequence": last_event.sequence,
                "state_history": history,
                "last_event_hash": last_event.event_hash,
                "state_hash": v["state_hash"],
                "total_events": len(events),
                "is_terminal": last_event.state in {"COMPLETED", "FAILED"},
            }
