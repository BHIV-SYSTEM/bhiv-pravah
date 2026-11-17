from __future__ import annotations

from control_plane.deployment.deployment_proof import DeploymentProofPacket
from control_plane.deployment.recovery_validator import RecoveryValidator
from control_plane.deployment.startup_validator import DeploymentPaths
from control_plane.persistence.append_only_log import AppendOnlyLog
from control_plane.persistence.hash_lineage_verifier import HashLineageVerifier
from control_plane.persistence.replay_index import ReplayIndex, SnapshotRegistry
from security.signed_trace import sign_trace, canonicalize

def _append_signed(journal, execution_id, event_id, state, timestamp, event_hash, previous_hash, source):
    trace_material = {
        "trace_id": event_id,
        "execution_id": execution_id,
        "parent_hash": previous_hash,
        "payload_hash": event_hash,
        "timestamp": float(timestamp),
        "signer": source,
    }
    sig = sign_trace(canonicalize(trace_material))
    journal.append(
        execution_id,
        event_id,
        state,
        timestamp,
        event_hash,
        previous_hash,
        source,
        {"signature": sig}
    )


def test_recovery_has_no_drift(tmp_path, phase6_artifact_dir):
    paths = DeploymentPaths(
        append_only_log_path=tmp_path / "append_only_log.jsonl",
        replay_index_path=tmp_path / "replay_index.json",
        snapshot_directory=tmp_path / "snapshots",
    )
    paths.snapshot_directory.mkdir(parents=True, exist_ok=True)

    journal = AppendOnlyLog(log_path=str(paths.append_only_log_path))
    _append_signed(journal, "phase6-recovery", "e1", "CREATED", 1, "h1", "", "system")
    _append_signed(journal, "phase6-recovery", "e2", "APPROVED", 2, "h2", "h1", "system")
    _append_signed(journal, "phase6-recovery", "e3", "EXECUTING", 3, "h3", "h2", "system")
    _append_signed(journal, "phase6-recovery", "e4", "COMPLETED", 4, "h4", "h3", "system")

    events = journal.get_execution_events("phase6-recovery")
    event_dicts = [
        {
            "sequence": event.sequence,
            "execution_id": event.execution_id,
            "event_id": event.event_id,
            "state": event.state,
            "timestamp": event.timestamp,
            "event_hash": event.event_hash,
            "previous_hash": event.previous_hash,
            "source": event.source,
            "details": event.details,
            "sequence_hash": event.sequence_hash,
            "lineage_proof": event.lineage_proof,
        }
        for event in events
    ]

    expected_state_hash = HashLineageVerifier().compute_execution_state_hash(event_dicts)

    ReplayIndex(index_path=str(paths.replay_index_path)).update_execution(
        execution_id="phase6-recovery",
        start_sequence=1,
        end_sequence=4,
        event_count=4,
        first_event_hash=events[0].event_hash,
        last_event_hash=events[-1].event_hash,
        last_timestamp=4,
        source_ids=["system"],
    )

    SnapshotRegistry(registry_path=str(tmp_path / "snapshot_registry.json")).register_snapshot(
        snapshot_id="phase6-snapshot",
        execution_id="phase6-recovery",
        at_sequence=4,
        state_hash=expected_state_hash,
        created_at=4,
    )

    paths.replay_index_path.unlink()

    validator = RecoveryValidator(paths=paths, proof_packet=DeploymentProofPacket(packet_dir=tmp_path / "proofs"))
    first = validator.validate("phase6-recovery", expected_state_hash=expected_state_hash)
    second = validator.validate("phase6-recovery", expected_state_hash=expected_state_hash)

    assert first.ready is True
    assert second.ready is True
    assert first.state_hash == expected_state_hash
    assert second.state_hash == expected_state_hash
    assert first.details["replay_index_loaded"] is True
    assert second.details["replay_index_loaded"] is True