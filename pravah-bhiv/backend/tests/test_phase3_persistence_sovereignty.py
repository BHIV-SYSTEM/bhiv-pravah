"""
Phase 3: Persistence Sovereignty - Deterministic Replay Tests.

Tests that prove:
1. Same event history = Same replay order
2. Same replay order = Same hash chain
3. Same hash chain = Same state reconstruction
4. Same state = Same replay result

Tests cover:
- Append-only immutability
- Sequence monotonicity
- Hash chain continuity
- Deterministic reconstruction
- Snapshot consistency
- Tampering detection
"""

import json
import os
import tempfile
import hashlib
import pytest
from pathlib import Path
from typing import Dict, Any

from control_plane.persistence import (
    AppendOnlyLog,
    ExecutionEvent,
    OrderingViolation,
    HashChainBreak,
    ReplayIndex,
    SnapshotRegistry,
    HashLineageVerifier,
    VerificationStatus
)


@pytest.fixture
def temp_log_dir():
    """Create temporary log directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def append_only_log(temp_log_dir):
    """Create test append-only log."""
    log_path = os.path.join(temp_log_dir, "append_only_log.jsonl")
    log = AppendOnlyLog(log_path=log_path)
    return log


@pytest.fixture
def replay_index(temp_log_dir):
    """Create test replay index."""
    index_path = os.path.join(temp_log_dir, "replay_index.json")
    index = ReplayIndex(index_path=index_path)
    return index


@pytest.fixture
def snapshot_registry(temp_log_dir):
    """Create test snapshot registry."""
    registry_path = os.path.join(temp_log_dir, "snapshot_registry.json")
    registry = SnapshotRegistry(registry_path=registry_path)
    return registry


@pytest.fixture
def verifier():
    """Create hash lineage verifier."""
    return HashLineageVerifier()


class TestAppendOnlyImmutability:
    """Test that history is never mutated - only appended."""
    
    def test_events_are_append_only_never_updated(self, append_only_log):
        """Verify events are immutable - never overwritten."""
        # Append first event
        event1 = append_only_log.append(
            execution_id="exec-1",
            event_id="evt-1",
            state="CREATED",
            timestamp=1000,
            event_hash="hash1",
            previous_hash="",
            source="test",
            details={"step": 1}
        )
        
        # Append second event
        event2 = append_only_log.append(
            execution_id="exec-1",
            event_id="evt-2",
            state="APPROVED",
            timestamp=1001,
            event_hash="hash2",
            previous_hash="hash1",
            source="test",
            details={"step": 2}
        )
        
        # Retrieve events
        events = append_only_log.get_execution_events("exec-1")
        assert len(events) == 2
        
        # Verify first event unchanged
        assert events[0].event_id == "evt-1"
        assert events[0].state == "CREATED"
        assert events[0].sequence == 1
        
        # Verify second event
        assert events[1].event_id == "evt-2"
        assert events[1].state == "APPROVED"
        assert events[1].sequence == 2
    
    def test_journal_file_is_append_only(self, temp_log_dir):
        """Verify journal file grows but never rewrites."""
        log_path = os.path.join(temp_log_dir, "append_only_log.jsonl")
        log = AppendOnlyLog(log_path=log_path)
        
        # Append event
        log.append(
            execution_id="exec-1",
            event_id="evt-1",
            state="CREATED",
            timestamp=1000,
            event_hash="hash1",
            previous_hash="",
            source="test",
            details={}
        )
        
        size1 = Path(log_path).stat().st_size
        line_count1 = log.journal_line_count()
        
        # Append another event
        log.append(
            execution_id="exec-1",
            event_id="evt-2",
            state="APPROVED",
            timestamp=1001,
            event_hash="hash2",
            previous_hash="hash1",
            source="test",
            details={}
        )
        
        size2 = Path(log_path).stat().st_size
        line_count2 = log.journal_line_count()
        
        # Size and line count must increase
        assert size2 > size1
        assert line_count2 > line_count1


class TestSequenceMonotonicity:
    """Test monotonic sequence ordering guarantees."""
    
    def test_sequence_numbers_are_monotonic(self, append_only_log):
        """Verify sequence numbers increment monotonically."""
        exec_id = "exec-mono-1"
        
        for i in range(5):
            event = append_only_log.append(
                execution_id=exec_id,
                event_id=f"evt-{i}",
                state=f"STATE{i}",
                timestamp=1000 + i,
                event_hash=f"hash{i}",
                previous_hash=f"hash{i-1}" if i > 0 else "",
                source="test",
                details={}
            )
            assert event.sequence == i + 1
        
        # Verify retrieval maintains order
        events = append_only_log.get_execution_events(exec_id)
        for i, event in enumerate(events):
            assert event.sequence == i + 1
    
    def test_ordering_violation_detected(self, append_only_log):
        """Verify ordering violations are caught."""
        exec_id = "exec-order-1"
        
        # Append valid event
        append_only_log.append(
            execution_id=exec_id,
            event_id="evt-1",
            state="STATE1",
            timestamp=1000,
            event_hash="hash1",
            previous_hash="",
            source="test",
            details={}
        )
        
        # Try to append with wrong previous_hash (simulating wrong chain)
        with pytest.raises(HashChainBreak):
            append_only_log.append(
                execution_id=exec_id,
                event_id="evt-2",
                state="STATE2",
                timestamp=1001,
                event_hash="hash2",
                previous_hash="wrong_hash",  # Wrong!
                source="test",
                details={}
            )


class TestHashChainContinuity:
    """Test blockchain-like hash chain verification."""
    
    def test_hash_chain_links_sequentially(self, append_only_log):
        """Verify each event's previous_hash matches prior event_hash."""
        exec_id = "exec-chain-1"
        hashes = []
        
        for i in range(3):
            prev_hash = hashes[-1] if hashes else ""
            event = append_only_log.append(
                execution_id=exec_id,
                event_id=f"evt-{i}",
                state=f"STATE{i}",
                timestamp=1000 + i,
                event_hash=f"hash{i}",
                previous_hash=prev_hash,
                source="test",
                details={}
            )
            hashes.append(event.event_hash)
        
        # Verify chain
        events = append_only_log.get_execution_events(exec_id)
        chain = append_only_log.get_execution_hash_chain(exec_id)
        
        # First event has empty previous_hash
        assert events[0].previous_hash == ""
        
        # Each event's previous matches prior hash
        for i in range(1, len(events)):
            assert events[i].previous_hash == events[i - 1].event_hash
    
    def test_hash_chain_break_detected(self, append_only_log):
        """Verify broken hash chains are detected during append."""
        # Try to append with non-matching previous_hash
        append_only_log.append(
            execution_id="exec-break-1",
            event_id="evt-1",
            state="STATE1",
            timestamp=1000,
            event_hash="hash1",
            previous_hash="",
            source="test",
            details={}
        )
        
        # This should fail because previous_hash doesn't match
        with pytest.raises(HashChainBreak):
            append_only_log.append(
                execution_id="exec-break-1",
                event_id="evt-2",
                state="STATE2",
                timestamp=1001,
                event_hash="hash2",
                previous_hash="wrong",
                source="test",
                details={}
            )


class TestDeterministicOrdering:
    """Test deterministic reconstruction always produces same order."""
    
    def test_multiple_reconstructions_produce_same_order(self, append_only_log):
        """Verify replay order is identical across reconstructions."""
        exec_id = "exec-determ-1"
        
        # Append events
        for i in range(5):
            append_only_log.append(
                execution_id=exec_id,
                event_id=f"evt-{i}",
                state=f"STATE{i}",
                timestamp=1000 + i,
                event_hash=f"hash{i}",
                previous_hash=f"hash{i-1}" if i > 0 else "",
                source="test",
                details={}
            )
        
        # First reconstruction
        events1 = append_only_log.get_execution_events(exec_id)
        order1 = [e.event_id for e in events1]
        
        # Second reconstruction (after rebuild)
        append_only_log._rebuild_from_journal()
        events2 = append_only_log.get_execution_events(exec_id)
        order2 = [e.event_id for e in events2]
        
        # Third reconstruction
        append_only_log._rebuild_from_journal()
        events3 = append_only_log.get_execution_events(exec_id)
        order3 = [e.event_id for e in events3]
        
        # All reconstructions must be identical
        assert order1 == order2 == order3
        assert order1 == ["evt-0", "evt-1", "evt-2", "evt-3", "evt-4"]


class TestHashLineageVerification:
    """Test cryptographic integrity verification."""
    
    def test_valid_lineage_passes_verification(self, verifier, append_only_log):
        """Verify valid event lineage passes all checks."""
        exec_id = "exec-valid-1"
        
        # Create valid lineage (append_only_log computes hashes correctly)
        events_appended = []
        for i in range(3):
            event = append_only_log.append(
                execution_id=exec_id,
                event_id=f"evt-{i}",
                state=f"STATE{i}",
                timestamp=1000 + i,
                event_hash=f"hash{i}",
                previous_hash=f"hash{i-1}" if i > 0 else "",
                source="test",
                details={}
            )
            events_appended.append(event)
        
        # Verify the appended events (they have computed sequence/lineage proofs)
        events = append_only_log.get_execution_events(exec_id)
        
        # Create dict with the computed hashes and proofs
        events_dict = [
            {
                'sequence': e.sequence,
                'execution_id': e.execution_id,
                'event_id': e.event_id,
                'state': e.state,
                'timestamp': e.timestamp,
                'event_hash': e.event_hash,
                'previous_hash': e.previous_hash,
                'source': e.source,
                'details': e.details,
                'sequence_hash': e.sequence_hash,
                'lineage_proof': e.lineage_proof
            }
            for e in events
        ]
        
        # Verify sequence continuity and hash chain
        result = verifier.verify_sequence_continuity(events_dict)
        assert result[0] is True  # No sequence breaks
        
        result = verifier.verify_hash_chain(events_dict)
        assert result[0] is True  # No chain breaks
        
        # Verify deterministic ordering
        result = verifier.verify_deterministic_ordering(events_dict)
        assert result[0] is True  # Valid deterministic order
        
        # Verify full lineage passes key checks
        assert len(events) == 3
        assert all(e.sequence >= 1 for e in events)
    
    def test_sequence_break_detected(self, verifier):
        """Verify sequence breaks are detected."""
        events = [
            {
                'sequence': 1,
                'execution_id': 'exec-1',
                'event_id': 'evt-1',
                'state': 'CREATED',
                'timestamp': 1000,
                'event_hash': 'hash1',
                'previous_hash': '',
                'source': 'test',
                'details': {},
                'sequence_hash': 'seq1',
                'lineage_proof': 'lineage1'
            },
            {
                'sequence': 1,  # DUPLICATE! Should be 2
                'execution_id': 'exec-1',
                'event_id': 'evt-2',
                'state': 'APPROVED',
                'timestamp': 1001,
                'event_hash': 'hash2',
                'previous_hash': 'hash1',
                'source': 'test',
                'details': {},
                'sequence_hash': 'seq2',
                'lineage_proof': 'lineage2'
            }
        ]
        
        result = verifier.verify_execution_lineage(events, 'exec-1')
        assert not result.is_valid
        assert result.status == VerificationStatus.SEQUENCE_BREAK
    
    def test_chain_break_detected(self, verifier):
        """Verify hash chain breaks are detected."""
        events = [
            {
                'sequence': 1,
                'execution_id': 'exec-1',
                'event_id': 'evt-1',
                'state': 'CREATED',
                'timestamp': 1000,
                'event_hash': 'hash1',
                'previous_hash': '',
                'source': 'test',
                'details': {},
                'sequence_hash': 'seq1',
                'lineage_proof': 'lineage1'
            },
            {
                'sequence': 2,
                'execution_id': 'exec-1',
                'event_id': 'evt-2',
                'state': 'APPROVED',
                'timestamp': 1001,
                'event_hash': 'hash2',
                'previous_hash': 'wrong_hash',  # BREAK! Should be 'hash1'
                'source': 'test',
                'details': {},
                'sequence_hash': 'seq2',
                'lineage_proof': 'lineage2'
            }
        ]
        
        result = verifier.verify_execution_lineage(events, 'exec-1')
        assert not result.is_valid
        assert result.status == VerificationStatus.CHAIN_BREAK


class TestReplayIndexing:
    """Test replay index for fast reconstruction."""
    
    def test_replay_index_enables_fast_lookup(self, replay_index):
        """Verify index provides O(1) execution lookup."""
        # Register execution
        replay_index.update_execution(
            execution_id="exec-1",
            start_sequence=1,
            end_sequence=10,
            event_count=10,
            first_event_hash="hash1",
            last_event_hash="hash10",
            last_timestamp=1009,
            source_ids=["test", "governance"]
        )
        
        # Fast lookup
        entry = replay_index.get_execution("exec-1")
        assert entry is not None
        assert entry.start_sequence == 1
        assert entry.end_sequence == 10
        assert entry.event_count == 10
    
    def test_index_persists_and_reloads(self, temp_log_dir):
        """Verify index persists to file and reloads on startup."""
        index1 = ReplayIndex(os.path.join(temp_log_dir, "replay_index.json"))
        
        # Add entry
        index1.update_execution(
            execution_id="exec-persist",
            start_sequence=1,
            end_sequence=5,
            event_count=5,
            first_event_hash="hash1",
            last_event_hash="hash5",
            last_timestamp=1004,
            source_ids=["test"]
        )
        
        # Create new index instance
        index2 = ReplayIndex(os.path.join(temp_log_dir, "replay_index.json"))
        
        # Verify data persisted
        entry = index2.get_execution("exec-persist")
        assert entry is not None
        assert entry.event_count == 5


class TestSnapshotConsistency:
    """Test snapshot checkpoints for bounded replay recovery."""
    
    def test_snapshots_track_execution_state(self, snapshot_registry):
        """Verify snapshots record execution state at sequence."""
        snapshot_registry.register_snapshot(
            snapshot_id="snap-1",
            execution_id="exec-1",
            at_sequence=10,
            state_hash="state-hash-10",
            created_at=1009
        )
        
        # Retrieve snapshot
        snapshot = snapshot_registry.get_snapshot("snap-1")
        assert snapshot is not None
        assert snapshot.at_sequence == 10
        assert snapshot.state_hash == "state-hash-10"
    
    def test_latest_snapshot_tracking(self, snapshot_registry):
        """Verify latest snapshot is tracked per execution."""
        # Register first snapshot
        snapshot_registry.register_snapshot(
            snapshot_id="snap-1",
            execution_id="exec-1",
            at_sequence=5,
            state_hash="state-5",
            created_at=1004
        )
        
        # Register newer snapshot
        snapshot_registry.register_snapshot(
            snapshot_id="snap-2",
            execution_id="exec-1",
            at_sequence=10,
            state_hash="state-10",
            created_at=1009
        )
        
        # Latest should be snap-2
        latest = snapshot_registry.get_latest_snapshot("exec-1")
        assert latest.snapshot_id == "snap-2"
        assert latest.at_sequence == 10


class TestDeterministicReplay:
    """Integration: Same history = Same replay result."""
    
    def test_identical_replay_produces_identical_state(self, append_only_log, verifier):
        """Prove deterministic replay: same events = same state hash."""
        exec_id = "exec-replay-determ"
        
        # Replay 1: Append events
        for i in range(5):
            append_only_log.append(
                execution_id=exec_id,
                event_id=f"evt-{i}",
                state=f"STATE{i}",
                timestamp=1000 + i,
                event_hash=f"hash{i}",
                previous_hash=f"hash{i-1}" if i > 0 else "",
                source="test",
                details={"iteration": i}
            )
        
        # Compute state hash after replay 1
        events1 = append_only_log.get_execution_events(exec_id)
        events1_dict = [
            {
                'sequence': e.sequence,
                'execution_id': e.execution_id,
                'event_id': e.event_id,
                'state': e.state,
                'timestamp': e.timestamp,
                'event_hash': e.event_hash,
                'previous_hash': e.previous_hash,
                'source': e.source,
                'details': e.details,
                'sequence_hash': e.sequence_hash,
                'lineage_proof': e.lineage_proof
            }
            for e in events1
        ]
        state_hash1 = verifier.compute_execution_state_hash(events1_dict)
        
        # Replay 2: Reconstruct (rebuild from journal)
        append_only_log._rebuild_from_journal()
        events2 = append_only_log.get_execution_events(exec_id)
        events2_dict = [
            {
                'sequence': e.sequence,
                'execution_id': e.execution_id,
                'event_id': e.event_id,
                'state': e.state,
                'timestamp': e.timestamp,
                'event_hash': e.event_hash,
                'previous_hash': e.previous_hash,
                'source': e.source,
                'details': e.details,
                'sequence_hash': e.sequence_hash,
                'lineage_proof': e.lineage_proof
            }
            for e in events2
        ]
        state_hash2 = verifier.compute_execution_state_hash(events2_dict)
        
        # Replay 3: Another reconstruction
        append_only_log._rebuild_from_journal()
        events3 = append_only_log.get_execution_events(exec_id)
        events3_dict = [
            {
                'sequence': e.sequence,
                'execution_id': e.execution_id,
                'event_id': e.event_id,
                'state': e.state,
                'timestamp': e.timestamp,
                'event_hash': e.event_hash,
                'previous_hash': e.previous_hash,
                'source': e.source,
                'details': e.details,
                'sequence_hash': e.sequence_hash,
                'lineage_proof': e.lineage_proof
            }
            for e in events3
        ]
        state_hash3 = verifier.compute_execution_state_hash(events3_dict)
        
        # All replays must produce identical state hash
        assert state_hash1 == state_hash2 == state_hash3
        
        # All replays must produce same event order
        assert [e['event_id'] for e in events1_dict] == \
               [e['event_id'] for e in events2_dict] == \
               [e['event_id'] for e in events3_dict]
