#!/usr/bin/env python3
"""
PRAVAH 50-Run SHA-256 Determinism Verification Script.
Executes an identical stream processing scenario 50 consecutive times from pristine state.
Verifies that 100% of runs yield identical SHA-256 state digests.

Output artifacts saved to:
review_packets/Evidence/50_run_determinism_proof.json
review_packets/Evidence/50_run_determinism_proof.log
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from pravah.replay_ledger import ReplayLedger, canonical_json_dump
from pravah.stream_processor import StreamProcessor


def run_single_scenario(run_id: int, temp_base_dir: Path) -> dict:
    run_dir = temp_base_dir / f"run_{run_id:02d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    log_path = run_dir / "journal.jsonl"
    index_path = run_dir / "index.json"
    
    ledger = ReplayLedger(log_path=str(log_path), index_path=str(index_path))
    processor = StreamProcessor(ledger=ledger)
    
    exec_id = "exec-deterministic-scenario-50"
    
    # 3 deterministic inbound signals
    signals = [
        {
            "schema_version": "1.0",
            "trace_id": "tr-determ-50",
            "execution_id": exec_id,
            "timestamp": "2026-11-17T12:00:01Z",
            "source": "governance_agent",
            "signal_type": "execution",
            "payload": {"step": "approve", "target_state": "APPROVED", "config": {"retry": 3}},
        },
        {
            "schema_version": "1.0",
            "trace_id": "tr-determ-50",
            "execution_id": exec_id,
            "timestamp": "2026-11-17T12:00:02Z",
            "source": "executor_worker",
            "signal_type": "execution",
            "payload": {"step": "execute", "target_state": "EXECUTED", "resources": {"cpu": 2.0}},
        },
        {
            "schema_version": "1.0",
            "trace_id": "tr-determ-50",
            "execution_id": exec_id,
            "timestamp": "2026-11-17T12:00:03Z",
            "source": "observer_sentinel",
            "signal_type": "verification",
            "payload": {"step": "complete", "target_state": "COMPLETED", "sla_verified": True},
        },
    ]
    
    start_time = time.perf_counter()
    results = processor.process_stream(signals)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    
    state = processor.get_state(exec_id)
    replay_proof = processor.replay(exec_id)
    
    # Canonical serialization of resulting state
    canonical_repr = canonical_json_dump(state)
    state_sha256 = hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()
    
    return {
        "run_id": run_id,
        "execution_id": exec_id,
        "sha256_hash": state_sha256,
        "state_hash": state["state_hash"],
        "last_event_hash": state["last_event_hash"],
        "sequence": state["sequence"],
        "events_count": len(results),
        "replay_valid": replay_proof["is_valid"],
        "replay_status": replay_proof["status"],
        "elapsed_ms": round(elapsed_ms, 3),
    }


def main():
    print("=" * 80)
    print("PRAVAH — 50-RUN SHA-256 DETERMINISM VERIFICATION")
    print("=" * 80)
    
    temp_dir = Path(tempfile.mkdtemp(prefix="pravah_determ_"))
    total_runs = 50
    run_records = []
    
    try:
        for i in range(1, total_runs + 1):
            record = run_single_scenario(i, temp_dir)
            run_records.append(record)
            print(f"Run {i:02d}/50: SHA-256={record['sha256_hash']} ({record['elapsed_ms']} ms) — Replay: {record['replay_status']}")
            
        first_hash = run_records[0]["sha256_hash"]
        first_state_hash = run_records[0]["state_hash"]
        all_match = all(r["sha256_hash"] == first_hash for r in run_records)
        all_state_match = all(r["state_hash"] == first_state_hash for r in run_records)
        all_valid = all(r["replay_valid"] for r in run_records)
        
        print("-" * 80)
        print(f"Total Runs Executed:       {total_runs}")
        print(f"Reference SHA-256:         {first_hash}")
        print(f"Cumulative State Hash:     {first_state_hash}")
        print(f"All Hashes Identical:      {all_match}")
        print(f"All Replays Valid:         {all_valid}")
        print("=" * 80)
        
        status = "PASSED" if (all_match and all_state_match and all_valid) else "FAILED"
        print(f"FINAL DETERMINISM VERDICT: {status}")
        
        summary = {
            "test_name": "50-run SHA-256 Determinism Verification",
            "status": status,
            "total_runs": total_runs,
            "reference_sha256_hash": first_hash,
            "reference_state_hash": first_state_hash,
            "identical_hash_rate": "100%" if all_match else "FAILED",
            "replay_integrity_rate": "100%" if all_valid else "FAILED",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "runs": run_records,
        }
        
        # Save output to evidence directories
        evidence_dirs = [
            Path("review_packets/Evidence"),
            backend_dir.parent / "review_packets" / "Evidence",
            backend_dir / "review_packets" / "Evidence",
        ]
        
        for ed in evidence_dirs:
            ed.mkdir(parents=True, exist_ok=True)
            json_file = ed / "50_run_determinism_proof.json"
            log_file = ed / "50_run_determinism_proof.log"
            
            with open(json_file, "w") as f:
                json.dump(summary, f, indent=2)
                
            with open(log_file, "w") as f:
                f.write(f"PRAVAH 50-RUN DETERMINISM PROOF LOG\n")
                f.write(f"Timestamp: {summary['timestamp']}\n")
                f.write(f"Verdict: {status}\n")
                f.write(f"Canonical State SHA-256: {first_hash}\n")
                f.write(f"Ledger State Hash: {first_state_hash}\n")
                f.write(f"Total Runs: {total_runs}\n\n")
                for r in run_records:
                    f.write(f"Run {r['run_id']:02d}: SHA256={r['sha256_hash']} state_hash={r['state_hash']} replay={r['replay_status']}\n")
                    
        print(f"Evidence artifacts successfully saved to review_packets/Evidence/")
        
        if not (all_match and all_valid):
            sys.exit(1)
            
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
