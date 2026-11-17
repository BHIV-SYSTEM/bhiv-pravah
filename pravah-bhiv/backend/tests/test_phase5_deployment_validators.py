from __future__ import annotations

import json
from pathlib import Path

from control_plane.deployment.deployment_proof import DeploymentProofPacket
from control_plane.deployment.healthcheck_replay import ReplayHealthcheck
from control_plane.deployment.readiness_validator import ReadinessValidator
from control_plane.deployment.recovery_validator import RecoveryValidator
from control_plane.deployment.startup_validator import DeploymentPaths, StartupValidator
from control_plane.persistence.append_only_log import AppendOnlyLog
from control_plane.persistence.hash_lineage_verifier import HashLineageVerifier
from control_plane.persistence.replay_index import ReplayIndex, SnapshotRegistry
from security.signed_trace import sign_trace, canonicalize


def _fake_ready_startup(monkeypatch, validator: StartupValidator) -> None:
    monkeypatch.setattr(validator, "redis_available", lambda: True)
    monkeypatch.setattr(validator, "policy_engine_loaded", lambda: True)
    monkeypatch.setattr(validator, "semantic_guard_loaded", lambda: True)


def _journal_event_dicts(events):
    return [
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


def test_startup_validator_reports_ready_when_artifacts_exist(tmp_path, monkeypatch):
    paths = DeploymentPaths(
        append_only_log_path=tmp_path / "append_only_log.jsonl",
        replay_index_path=tmp_path / "replay_index.json",
        snapshot_directory=tmp_path / "snapshots",
        redis_host="127.0.0.1",
        redis_port=6399,
    )
    paths.snapshot_directory.mkdir(parents=True)
    paths.append_only_log_path.write_text("{}\n", encoding="utf-8")
    paths.replay_index_path.write_text("{}", encoding="utf-8")

    packet = DeploymentProofPacket(packet_dir=tmp_path / "packet")
    validator = StartupValidator(paths=paths, proof_packet=packet)
    _fake_ready_startup(monkeypatch, validator)

    result = validator.validate()

    assert result.ready is True
    assert result.status == "READY"
    assert all(result.checks.values())


def test_startup_validator_flags_missing_append_only_log(tmp_path, monkeypatch):
    paths = DeploymentPaths(
        append_only_log_path=tmp_path / "missing.jsonl",
        replay_index_path=tmp_path / "replay_index.json",
        snapshot_directory=tmp_path / "snapshots",
        redis_host="127.0.0.1",
        redis_port=6399,
    )
    paths.snapshot_directory.mkdir(parents=True)
    paths.replay_index_path.write_text("{}", encoding="utf-8")

    validator = StartupValidator(paths=paths, proof_packet=DeploymentProofPacket(packet_dir=tmp_path / "packet"))
    _fake_ready_startup(monkeypatch, validator)

    result = validator.validate()

    assert result.ready is False
    assert result.status == "SERVICE NOT READY"
    assert result.checks["append_only_log_exists"] is False


def test_readiness_validator_returns_required_payload(tmp_path, monkeypatch):
    paths = DeploymentPaths(
        append_only_log_path=tmp_path / "append_only_log.jsonl",
        replay_index_path=tmp_path / "replay_index.json",
        snapshot_directory=tmp_path / "snapshots",
    )
    paths.snapshot_directory.mkdir(parents=True)
    paths.append_only_log_path.write_text("{}\n", encoding="utf-8")
    paths.replay_index_path.write_text("{}", encoding="utf-8")

    packet = DeploymentProofPacket(packet_dir=tmp_path / "packet")
    validator = ReadinessValidator(paths=paths, proof_packet=packet)
    _fake_ready_startup(monkeypatch, validator.startup_validator)

    result = validator.validate()

    assert result.ready is True
    assert result.status == "READY"
    assert result.readiness == {
        "phase1_signed_lineage": True,
        "phase2_policy_engine": True,
        "phase3_persistence": True,
        "phase4_semantic_guard": True,
        "replay_index_loaded": True,
    }


def test_recovery_validator_validates_restart_determinism(tmp_path):
    paths = DeploymentPaths(
        append_only_log_path=tmp_path / "append_only_log.jsonl",
        replay_index_path=tmp_path / "replay_index.json",
        snapshot_directory=tmp_path / "snapshots",
    )
    paths.snapshot_directory.mkdir(parents=True)
    packet = DeploymentProofPacket(packet_dir=tmp_path / "packet")

    journal = AppendOnlyLog(log_path=str(paths.append_only_log_path))
    _append_signed(journal, "exec123", "e1", "CREATED", 1, "h1", "", "system")
    _append_signed(journal, "exec123", "e2", "APPROVED", 2, "h2", "h1", "system")
    _append_signed(journal, "exec123", "e3", "EXECUTING", 3, "h3", "h2", "system")
    _append_signed(journal, "exec123", "e4", "COMPLETED", 4, "h4", "h3", "system")

    events = journal.get_execution_events("exec123")
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

    verifier = HashLineageVerifier()
    state_hash = verifier.compute_execution_state_hash(event_dicts)

    replay_index = ReplayIndex(index_path=str(paths.replay_index_path))
    replay_index.update_execution(
        execution_id="exec123",
        start_sequence=1,
        end_sequence=4,
        event_count=4,
        first_event_hash=events[0].event_hash,
        last_event_hash=events[-1].event_hash,
        last_timestamp=4,
        source_ids=["system"],
    )

    snapshots = SnapshotRegistry(registry_path=str(tmp_path / "snapshot_registry.json"))
    snapshots.register_snapshot(
        snapshot_id="snap1",
        execution_id="exec123",
        at_sequence=4,
        state_hash=state_hash,
        created_at=4,
    )

    result = RecoveryValidator(paths=paths, proof_packet=packet).validate("exec123", expected_state_hash=state_hash)

    assert result.ready is True
    assert result.status == "READY"
    assert result.state_hash == state_hash
    assert result.journal_records == 4


def test_healthcheck_replay_wraps_recovery_result(tmp_path):
    paths = DeploymentPaths(
        append_only_log_path=tmp_path / "append_only_log.jsonl",
        replay_index_path=tmp_path / "replay_index.json",
        snapshot_directory=tmp_path / "snapshots",
    )
    paths.snapshot_directory.mkdir(parents=True)
    packet = DeploymentProofPacket(packet_dir=tmp_path / "packet")

    journal = AppendOnlyLog(log_path=str(paths.append_only_log_path))
    _append_signed(journal, "exec123", "e1", "CREATED", 1, "h1", "", "system")
    _append_signed(journal, "exec123", "e2", "APPROVED", 2, "h2", "h1", "system")
    _append_signed(journal, "exec123", "e3", "EXECUTING", 3, "h3", "h2", "system")

    events = journal.get_execution_events("exec123")
    event_dicts = [{"sequence": e.sequence, "execution_id": e.execution_id, "event_id": e.event_id, "state": e.state, "timestamp": e.timestamp, "event_hash": e.event_hash, "previous_hash": e.previous_hash, "source": e.source, "details": e.details, "sequence_hash": e.sequence_hash, "lineage_proof": e.lineage_proof} for e in events]
    state_hash = HashLineageVerifier().compute_execution_state_hash(event_dicts)

    ReplayIndex(index_path=str(paths.replay_index_path)).update_execution(
        execution_id="exec123",
        start_sequence=1,
        end_sequence=3,
        event_count=3,
        first_event_hash=events[0].event_hash,
        last_event_hash=events[-1].event_hash,
        last_timestamp=3,
        source_ids=["system"],
    )

    SnapshotRegistry(registry_path=str(tmp_path / "snapshot_registry.json")).register_snapshot(
        snapshot_id="snap1",
        execution_id="exec123",
        at_sequence=3,
        state_hash=state_hash,
        created_at=3,
    )

    result = ReplayHealthcheck(paths=paths, proof_packet=packet).check("exec123", expected_state_hash=state_hash)

    assert result.healthy is True
    assert result.status == "READY"
    assert result.recovery.ready is True


def test_restart_rebuild_preserves_state(tmp_path):
    paths = DeploymentPaths(
        append_only_log_path=tmp_path / "append_only_log.jsonl",
        replay_index_path=tmp_path / "replay_index.json",
        snapshot_directory=tmp_path / "snapshots",
    )
    paths.snapshot_directory.mkdir(parents=True)
    packet = DeploymentProofPacket(packet_dir=tmp_path / "packet")

    journal = AppendOnlyLog(log_path=str(paths.append_only_log_path))
    _append_signed(journal, "exec-restart", "e1", "CREATED", 1, "h1", "", "system")
    _append_signed(journal, "exec-restart", "e2", "APPROVED", 2, "h2", "h1", "system")
    _append_signed(journal, "exec-restart", "e3", "EXECUTING", 3, "h3", "h2", "system")
    _append_signed(journal, "exec-restart", "e4", "COMPLETED", 4, "h4", "h3", "system")

    events = journal.get_execution_events("exec-restart")
    event_dicts = _journal_event_dicts(events)
    original_state_hash = HashLineageVerifier().compute_execution_state_hash(event_dicts)

    ReplayIndex(index_path=str(paths.replay_index_path)).update_execution(
        execution_id="exec-restart",
        start_sequence=1,
        end_sequence=4,
        event_count=4,
        first_event_hash=events[0].event_hash,
        last_event_hash=events[-1].event_hash,
        last_timestamp=4,
        source_ids=["system"],
    )

    SnapshotRegistry(registry_path=str(tmp_path / "snapshot_registry.json")).register_snapshot(
        snapshot_id="snap-restart",
        execution_id="exec-restart",
        at_sequence=4,
        state_hash=original_state_hash,
        created_at=4,
    )

    paths.replay_index_path.unlink()

    result = RecoveryValidator(paths=paths, proof_packet=packet).validate("exec-restart", expected_state_hash=original_state_hash)

    assert result.ready is True
    assert result.status == "READY"
    assert result.state_hash == original_state_hash
    assert result.details["replay_index_loaded"] is True
    assert paths.replay_index_path.exists()


def test_recovery_fails_on_corrupted_journal(tmp_path):
    paths = DeploymentPaths(
        append_only_log_path=tmp_path / "append_only_log.jsonl",
        replay_index_path=tmp_path / "replay_index.json",
        snapshot_directory=tmp_path / "snapshots",
    )
    paths.snapshot_directory.mkdir(parents=True)
    packet = DeploymentProofPacket(packet_dir=tmp_path / "packet")

    journal = AppendOnlyLog(log_path=str(paths.append_only_log_path))
    _append_signed(journal, "exec-corrupt", "e1", "CREATED", 1, "h1", "", "system")
    _append_signed(journal, "exec-corrupt", "e2", "APPROVED", 2, "h2", "h1", "system")
    _append_signed(journal, "exec-corrupt", "e3", "EXECUTING", 3, "h3", "h2", "system")

    events = journal.get_execution_events("exec-corrupt")
    expected_state_hash = HashLineageVerifier().compute_execution_state_hash(_journal_event_dicts(events))

    ReplayIndex(index_path=str(paths.replay_index_path)).update_execution(
        execution_id="exec-corrupt",
        start_sequence=1,
        end_sequence=3,
        event_count=3,
        first_event_hash=events[0].event_hash,
        last_event_hash=events[-1].event_hash,
        last_timestamp=3,
        source_ids=["system"],
    )

    SnapshotRegistry(registry_path=str(tmp_path / "snapshot_registry.json")).register_snapshot(
        snapshot_id="snap-corrupt",
        execution_id="exec-corrupt",
        at_sequence=3,
        state_hash=expected_state_hash,
        created_at=3,
    )

    journal_path = Path(paths.append_only_log_path)
    records = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records[-1]["event"]["event_hash"] = "corrupted-hash"
    
    trace_material = {
        "trace_id": records[-1]["event"]["event_id"],
        "execution_id": records[-1]["event"]["execution_id"],
        "parent_hash": records[-1]["event"]["previous_hash"],
        "payload_hash": "corrupted-hash",
        "timestamp": float(records[-1]["event"]["timestamp"]),
        "signer": records[-1]["event"]["source"],
    }
    records[-1]["event"]["details"]["signature"] = sign_trace(canonicalize(trace_material))
    
    journal_path.write_text("\n".join(json.dumps(record, separators=(",", ":")) for record in records) + "\n", encoding="utf-8")

    result = RecoveryValidator(paths=paths, proof_packet=packet).validate("exec-corrupt", expected_state_hash=expected_state_hash)

    assert result.ready is False
    assert result.status == "RECOVERY_FAILED"
    assert "state_hash_mismatch" in result.failures