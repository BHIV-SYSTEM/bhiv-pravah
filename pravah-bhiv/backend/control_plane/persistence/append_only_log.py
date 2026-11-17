"""
Phase 3: Append-Only Immutable Execution Journal

Deterministic event sourcing with:
- Monotonic sequence numbers
- Hash-chain linkage
- Append-only writes (never mutate history)
- Deterministic ordering guarantees
- Replay-safe persistence
"""

import hashlib
import json
import os
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


@dataclass(frozen=True)
class ExecutionEvent:
    """Immutable execution event with deterministic ordering."""
    
    sequence: int  # Monotonic sequence per execution_id
    execution_id: str
    event_id: str
    state: str
    timestamp: int
    event_hash: str
    previous_hash: str
    source: str
    details: Dict[str, Any]
    
    # Phase 3 additions
    sequence_hash: str  # Hash of (sequence, execution_id) for ordering integrity
    lineage_proof: str  # Hash of (event_hash, previous_hash, sequence) for chain verification


@dataclass(frozen=True)
class AppendOnlyRecord:
    """Immutable append-only record in the journal."""
    
    record_sequence: int  # Global record sequence (across all executions)
    event: ExecutionEvent
    written_at: int  # Timestamp when written to journal


class OrderingViolation(Exception):
    """Raised when monotonic sequence ordering is violated."""
    pass


class HashChainBreak(Exception):
    """Raised when hash chain linkage is corrupted."""
    pass


class AppendOnlyLog:
    """
    Cryptographically verifiable append-only execution journal.
    
    Guarantees:
    - Append-only writes (never UPDATE or DELETE)
    - Monotonic sequence numbers per execution
    - Hash chain continuity
    - Deterministic event ordering
    - Replay-safe persistence
    """
    
    def __init__(self, log_path: str = "logs/control_plane/append_only_log.jsonl"):
        """Initialize append-only journal."""
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory caches (rebuilt from journal on startup)
        self._execution_sequences: Dict[str, int] = {}  # execution_id -> max sequence
        self._execution_last_hashes: Dict[str, str] = {}  # execution_id -> last event_hash
        self._record_sequence = 0  # Global record counter
        
        # Thread-safety
        self._lock = threading.RLock()
        
        # Rebuild state from existing journal
        self._rebuild_from_journal()
    
    def _rebuild_from_journal(self) -> None:
        """Rebuild in-memory state from append-only journal."""
        if not self.log_path.exists():
            return
        
        with self._lock:
            self._execution_sequences.clear()
            self._execution_last_hashes.clear()
            self._record_sequence = 0
            
            with open(self.log_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        self._record_sequence = max(
                            self._record_sequence,
                            record['record_sequence']
                        )
                        event_data = record['event']
                        execution_id = event_data['execution_id']
                        sequence = event_data['sequence']
                        event_hash = event_data['event_hash']
                        
                        # Track max sequence
                        self._execution_sequences[execution_id] = max(
                            self._execution_sequences.get(execution_id, 0),
                            sequence
                        )
                        # Track last hash
                        self._execution_last_hashes[execution_id] = event_hash
                    except (json.JSONDecodeError, KeyError):
                        # Skip corrupted lines
                        pass
    
    def append(
        self,
        execution_id: str,
        event_id: str,
        state: str,
        timestamp: int,
        event_hash: str,
        previous_hash: str,
        source: str,
        details: Dict[str, Any]
    ) -> ExecutionEvent:
        """
        Append immutable event to journal.
        
        Never mutates existing events. Only appends new ones.
        Validates:
        - Monotonic sequence
        - Hash chain continuity
        - Ordering integrity
        
        Raises:
        - OrderingViolation: If sequence not monotonic
        - HashChainBreak: If hash chain corrupted
        """
        with self._lock:
            # Get next sequence for this execution
            current_max_seq = self._execution_sequences.get(execution_id, 0)
            next_sequence = current_max_seq + 1
            
            # Verify hash chain continuity
            expected_previous = self._execution_last_hashes.get(execution_id, "")
            if expected_previous != previous_hash:
                raise HashChainBreak(
                    f"Hash chain break for {execution_id}: "
                    f"expected previous_hash={expected_previous}, "
                    f"got={previous_hash}"
                )
            
            # Build sequence hash (proof of ordering)
            sequence_proof = f"{next_sequence}:{execution_id}:{event_hash}"
            sequence_hash = hashlib.sha256(sequence_proof.encode()).hexdigest()
            
            # Build lineage proof (proof of chain integrity)
            lineage_proof_data = f"{event_hash}:{previous_hash}:{next_sequence}"
            lineage_proof = hashlib.sha256(lineage_proof_data.encode()).hexdigest()
            
            # Create immutable event
            event = ExecutionEvent(
                sequence=next_sequence,
                execution_id=execution_id,
                event_id=event_id,
                state=state,
                timestamp=timestamp,
                event_hash=event_hash,
                previous_hash=previous_hash,
                source=source,
                details=details,
                sequence_hash=sequence_hash,
                lineage_proof=lineage_proof
            )
            
            # Create append-only record
            self._record_sequence += 1
            record = AppendOnlyRecord(
                record_sequence=self._record_sequence,
                event=event,
                written_at=int(datetime.utcnow().timestamp())
            )
            
            # Write to journal (APPEND ONLY - never overwrite)
            record_dict = {
                'record_sequence': record.record_sequence,
                'event': asdict(event),
                'written_at': record.written_at
            }
            
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(record_dict, separators=(',', ':')) + '\n')
            
            # Update in-memory state
            self._execution_sequences[execution_id] = next_sequence
            self._execution_last_hashes[execution_id] = event_hash
            
            return event
    
    def get_execution_events(self, execution_id: str) -> List[ExecutionEvent]:
        """Get all events for an execution in deterministic order (by sequence)."""
        events = []
        
        if not self.log_path.exists():
            return events
        
        with self._lock:
            with open(self.log_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        event_data = record['event']
                        if event_data['execution_id'] == execution_id:
                            event = ExecutionEvent(
                                sequence=event_data['sequence'],
                                execution_id=event_data['execution_id'],
                                event_id=event_data['event_id'],
                                state=event_data['state'],
                                timestamp=event_data['timestamp'],
                                event_hash=event_data['event_hash'],
                                previous_hash=event_data['previous_hash'],
                                source=event_data['source'],
                                details=event_data['details'],
                                sequence_hash=event_data['sequence_hash'],
                                lineage_proof=event_data['lineage_proof']
                            )
                            events.append(event)
                    except (json.JSONDecodeError, KeyError):
                        pass
        
        # Sort by sequence (deterministic ordering)
        return sorted(events, key=lambda e: e.sequence)
    
    def get_last_event(self, execution_id: str) -> Optional[ExecutionEvent]:
        """Get the last appended event for an execution."""
        events = self.get_execution_events(execution_id)
        return events[-1] if events else None
    
    def get_execution_hash_chain(self, execution_id: str) -> List[Tuple[int, str, str]]:
        """
        Get hash chain for execution: (sequence, event_hash, lineage_proof).
        
        Returns list of (sequence, event_hash, lineage_proof) tuples.
        Deterministically ordered by sequence.
        """
        events = self.get_execution_events(execution_id)
        return [(e.sequence, e.event_hash, e.lineage_proof) for e in events]
    
    def count_events(self, execution_id: str) -> int:
        """Get total event count for execution."""
        return len(self.get_execution_events(execution_id))
    
    def get_all_execution_ids(self) -> List[str]:
        """Get all unique execution IDs in journal."""
        execution_ids = set()
        
        if not self.log_path.exists():
            return []
        
        with self._lock:
            with open(self.log_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        execution_id = record['event']['execution_id']
                        execution_ids.add(execution_id)
                    except (json.JSONDecodeError, KeyError):
                        pass
        
        return sorted(list(execution_ids))
    
    def verify_execution_ordering(self, execution_id: str) -> bool:
        """
        Verify monotonic sequence ordering for execution.
        
        Raises OrderingViolation if any sequence breaks.
        """
        events = self.get_execution_events(execution_id)
        
        previous_seq = 0
        for event in events:
            if event.sequence <= previous_seq:
                raise OrderingViolation(
                    f"Sequence violation in {execution_id}: "
                    f"expected > {previous_seq}, got {event.sequence}"
                )
            previous_seq = event.sequence
        
        return True
    
    def verify_hash_continuity(self, execution_id: str) -> bool:
        """
        Verify hash chain continuity for execution.
        
        Raises HashChainBreak if any link is broken.
        """
        events = self.get_execution_events(execution_id)
        
        for i, event in enumerate(events):
            if i == 0:
                # First event should have empty previous_hash
                if event.previous_hash != "":
                    raise HashChainBreak(
                        f"First event {event.event_id} has non-empty previous_hash"
                    )
            else:
                # Each event's previous_hash must match prior event's hash
                prior_event = events[i - 1]
                if event.previous_hash != prior_event.event_hash:
                    raise HashChainBreak(
                        f"Hash chain break between events {i-1} and {i}: "
                        f"event {event.event_id} has previous_hash={event.previous_hash}, "
                        f"but prior event {prior_event.event_id} has event_hash={prior_event.event_hash}"
                    )
        
        return True
    
    def journal_size_bytes(self) -> int:
        """Get journal file size in bytes."""
        if not self.log_path.exists():
            return 0
        return self.log_path.stat().st_size
    
    def journal_line_count(self) -> int:
        """Get number of records in journal."""
        if not self.log_path.exists():
            return 0
        
        count = 0
        with open(self.log_path, 'r') as f:
            for _ in f:
                count += 1
        return count
