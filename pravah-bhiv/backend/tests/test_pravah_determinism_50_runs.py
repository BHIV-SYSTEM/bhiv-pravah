"""
Automated Pytest for 50-Run SHA-256 Determinism Verification
"""

import hashlib
import json
from pathlib import Path
from pravah.replay_ledger import ReplayLedger, canonical_json_dump
from pravah.stream_processor import StreamProcessor


def test_50_consecutive_runs_sha256_invariance(tmp_path):
    """
    Executes 50 independent runs from clean state and asserts 100% SHA-256 invariance.
    """
    hashes = []
    state_hashes = []
    
    signals = [
        {
            "schema_version": "1.0",
            "trace_id": "tr-50-run",
            "execution_id": "exec-pytest-50",
            "timestamp": "2026-11-17T12:00:01Z",
            "source": "governance_agent",
            "signal_type": "execution",
            "payload": {"step": "approve", "target_state": "APPROVED"},
        },
        {
            "schema_version": "1.0",
            "trace_id": "tr-50-run",
            "execution_id": "exec-pytest-50",
            "timestamp": "2026-11-17T12:00:02Z",
            "source": "executor_worker",
            "signal_type": "execution",
            "payload": {"step": "execute", "target_state": "EXECUTED"},
        },
        {
            "schema_version": "1.0",
            "trace_id": "tr-50-run",
            "execution_id": "exec-pytest-50",
            "timestamp": "2026-11-17T12:00:03Z",
            "source": "observer_sentinel",
            "signal_type": "verification",
            "payload": {"step": "complete", "target_state": "COMPLETED"},
        },
    ]

    for i in range(50):
        run_log = tmp_path / f"run_{i}.jsonl"
        run_idx = tmp_path / f"run_{i}.json"
        
        ledger = ReplayLedger(log_path=str(run_log), index_path=str(run_idx))
        processor = StreamProcessor(ledger=ledger)
        
        processor.process_stream(signals)
        state = processor.get_state("exec-pytest-50")
        
        canonical_state = canonical_json_dump(state)
        run_sha256 = hashlib.sha256(canonical_state.encode("utf-8")).hexdigest()
        
        hashes.append(run_sha256)
        state_hashes.append(state["state_hash"])

    # Verify all 50 hashes are identical
    assert len(set(hashes)) == 1, f"Found divergent hashes: {set(hashes)}"
    assert len(set(state_hashes)) == 1, f"Found divergent state_hashes: {set(state_hashes)}"
