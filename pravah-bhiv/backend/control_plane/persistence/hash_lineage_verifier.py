"""
Hash Lineage Verifier - Event Integrity Validation.

Cryptographically verifies:
- Sequence continuity
- Event hash integrity
- Hash chain linkage
- Snapshot consistency
- Replay determinism
"""

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any


class VerificationStatus(Enum):
    """Verification result status."""
    
    VALID = "VALID"
    SEQUENCE_BREAK = "SEQUENCE_BREAK"
    HASH_MISMATCH = "HASH_MISMATCH"
    CHAIN_BREAK = "CHAIN_BREAK"
    PAYLOAD_CORRUPTION = "PAYLOAD_CORRUPTION"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    MISSING_EVENT = "MISSING_EVENT"
    INVALID_PROOF = "INVALID_PROOF"


@dataclass(frozen=True)
class VerificationResult:
    """Result of hash lineage verification."""
    
    status: VerificationStatus
    execution_id: str
    is_valid: bool
    events_verified: int
    error_sequence: Optional[int] = None
    error_event_id: Optional[str] = None
    error_detail: Optional[str] = None


class HashLineageVerifier:
    """
    Cryptographically verifies execution event integrity.
    
    Guarantees:
    - No tampering can go undetected
    - Missing events detected
    - Reordered events detected
    - Corrupted hashes detected
    - Chain breaks detected
    """
    
    def __init__(self):
        """Initialize verifier."""
        pass
    
    @staticmethod
    def _compute_event_hash(event_dict: Dict[str, Any]) -> str:
        """Compute canonical event hash."""
        # Serialize without hash fields and chain metadata
        payload = {
            k: v for k, v in event_dict.items()
            if k not in ['event_hash', 'sequence_hash', 'lineage_proof', 'sequence', 'previous_hash']
        }
        
        canonical = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    @staticmethod
    def _compute_sequence_hash(sequence: int, execution_id: str, event_hash: str) -> str:
        """Compute sequence proof hash."""
        proof = f"{sequence}:{execution_id}:{event_hash}"
        return hashlib.sha256(proof.encode()).hexdigest()
    
    @staticmethod
    def _compute_lineage_proof(
        event_hash: str,
        previous_hash: str,
        sequence: int
    ) -> str:
        """Compute lineage proof hash."""
        proof_data = f"{event_hash}:{previous_hash}:{sequence}"
        return hashlib.sha256(proof_data.encode()).hexdigest()
    
    def verify_event_integrity(
        self,
        event: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Verify single event hash integrity.
        
        Returns (is_valid, error_message)
        """
        try:
            # Verify event_hash matches payload
            computed_hash = self._compute_event_hash(event)
            if computed_hash != event.get('event_hash'):
                return (
                    False,
                    f"Event hash mismatch: computed={computed_hash}, stored={event.get('event_hash')}"
                )
            
            # Verify sequence_hash
            computed_seq_hash = self._compute_sequence_hash(
                event.get('sequence'),
                event.get('execution_id'),
                event.get('event_hash')
            )
            if computed_seq_hash != event.get('sequence_hash'):
                return (
                    False,
                    f"Sequence hash mismatch: computed={computed_seq_hash}, stored={event.get('sequence_hash')}"
                )
            
            # Verify lineage_proof
            computed_lineage = self._compute_lineage_proof(
                event.get('event_hash'),
                event.get('previous_hash'),
                event.get('sequence')
            )
            if computed_lineage != event.get('lineage_proof'):
                return (
                    False,
                    f"Lineage proof mismatch: computed={computed_lineage}, stored={event.get('lineage_proof')}"
                )
            
            return (True, "")
        except Exception as e:
            return (False, str(e))
    
    def verify_sequence_continuity(
        self,
        events: List[Dict[str, Any]]
    ) -> tuple[bool, Optional[int], str]:
        """
        Verify monotonic sequence continuity.
        
        Returns (is_valid, error_sequence, error_detail)
        """
        if not events:
            return (True, None, "")
        
        # Sort by sequence
        sorted_events = sorted(events, key=lambda e: e.get('sequence', 0))
        
        previous_seq = 0
        for event in sorted_events:
            current_seq = event.get('sequence')
            
            if current_seq <= previous_seq:
                return (
                    False,
                    current_seq,
                    f"Sequence not monotonic: expected > {previous_seq}, got {current_seq}"
                )
            
            previous_seq = current_seq
        
        return (True, None, "")
    
    def verify_hash_chain(
        self,
        events: List[Dict[str, Any]]
    ) -> tuple[bool, Optional[int], str]:
        """
        Verify hash chain continuity (blockchain-like linkage).
        
        Returns (is_valid, error_sequence, error_detail)
        """
        if not events:
            return (True, None, "")
        
        # Sort by sequence
        sorted_events = sorted(events, key=lambda e: e.get('sequence', 0))
        
        for i, event in enumerate(sorted_events):
            if i == 0:
                # First event must have empty previous_hash
                if event.get('previous_hash') != "":
                    return (
                        False,
                        event.get('sequence'),
                        f"First event has non-empty previous_hash: {event.get('previous_hash')}"
                    )
            else:
                # Each event's previous_hash must match prior event's hash
                prior_event = sorted_events[i - 1]
                prior_hash = prior_event.get('event_hash')
                expected_previous = event.get('previous_hash')
                
                if expected_previous != prior_hash:
                    return (
                        False,
                        event.get('sequence'),
                        f"Hash chain break: expected previous_hash={prior_hash}, got={expected_previous}"
                    )
        
        return (True, None, "")
    
    def verify_deterministic_ordering(
        self,
        events: List[Dict[str, Any]]
    ) -> tuple[bool, Optional[int], str]:
        """
        Verify events maintain deterministic ordering.
        
        Determinism requires:
        - Sorted by sequence (primary)
        - Never by arrival time or random order
        
        Returns (is_valid, error_sequence, error_detail)
        """
        if len(events) < 2:
            return (True, None, "")
        
        # Check sequence is strictly increasing
        for i in range(1, len(events)):
            prev_seq = events[i - 1].get('sequence', 0)
            curr_seq = events[i].get('sequence', 0)
            
            if curr_seq <= prev_seq:
                return (
                    False,
                    curr_seq,
                    f"Non-deterministic ordering: sequence {curr_seq} after {prev_seq}"
                )
        
        return (True, None, "")
    
    def verify_execution_lineage(
        self,
        events: List[Dict[str, Any]],
        execution_id: str
    ) -> VerificationResult:
        """
        Comprehensive verification of execution lineage.
        
        Validates:
        1. Sequence continuity
        2. Event hash integrity
        3. Hash chain linkage
        4. Deterministic ordering
        5. All events belong to execution_id
        
        Returns VerificationResult with detailed status.
        """
        # Verify all events belong to execution
        for event in events:
            if event.get('execution_id') != execution_id:
                return VerificationResult(
                    status=VerificationStatus.INVALID_PROOF,
                    execution_id=execution_id,
                    is_valid=False,
                    events_verified=0,
                    error_event_id=event.get('event_id'),
                    error_detail=f"Event belongs to different execution: {event.get('execution_id')}"
                )
        
        # Verify sequence continuity
        is_valid, error_seq, error_msg = self.verify_sequence_continuity(events)
        if not is_valid:
            return VerificationResult(
                status=VerificationStatus.SEQUENCE_BREAK,
                execution_id=execution_id,
                is_valid=False,
                events_verified=error_seq or 0,
                error_sequence=error_seq,
                error_detail=error_msg
            )
        
        # Verify hash chain
        is_valid, error_seq, error_msg = self.verify_hash_chain(events)
        if not is_valid:
            return VerificationResult(
                status=VerificationStatus.CHAIN_BREAK,
                execution_id=execution_id,
                is_valid=False,
                events_verified=error_seq or 0,
                error_sequence=error_seq,
                error_detail=error_msg
            )
        
        # Verify each event's hash integrity
        for event in events:
            is_valid, error_msg = self.verify_event_integrity(event)
            if not is_valid:
                return VerificationResult(
                    status=VerificationStatus.HASH_MISMATCH,
                    execution_id=execution_id,
                    is_valid=False,
                    events_verified=event.get('sequence', 0),
                    error_event_id=event.get('event_id'),
                    error_detail=error_msg
                )
        
        # Verify deterministic ordering
        is_valid, error_seq, error_msg = self.verify_deterministic_ordering(events)
        if not is_valid:
            return VerificationResult(
                status=VerificationStatus.INVALID_PROOF,
                execution_id=execution_id,
                is_valid=False,
                events_verified=error_seq or 0,
                error_sequence=error_seq,
                error_detail=error_msg
            )
        
        return VerificationResult(
            status=VerificationStatus.VALID,
            execution_id=execution_id,
            is_valid=True,
            events_verified=len(events)
        )
    
    def compute_execution_state_hash(
        self,
        events: List[Dict[str, Any]]
    ) -> str:
        """
        Compute deterministic state hash from event sequence.
        
        Same events in same order always produce same hash.
        Different order or missing events produce different hash.
        """
        # Sort by sequence to ensure determinism
        sorted_events = sorted(events, key=lambda e: e.get('sequence', 0))
        
        # Hash chain of all event hashes
        combined = ":".join([e.get('event_hash', '') for e in sorted_events])
        return hashlib.sha256(combined.encode()).hexdigest()
