from __future__ import annotations

import json

import pytest

from control_plane.core import execution_lineage as lineage_module
from control_plane.core.execution_lineage import append_lineage_event, replay_execution_lineage
from security.lineage_verifier import PayloadHashMismatchError


def _tamper_lineage_record(log_path, execution_id: str) -> None:
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for record in records:
        if record.get("execution_id") == execution_id and record.get("state") == "APPROVED":
            record["details"] = {"tampered": True}
            break
    log_path.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n", encoding="utf-8")


def test_tampered_replay_is_rejected(monkeypatch, tmp_path, phase6_artifact_dir):
    log_path = tmp_path / "execution_lineage.jsonl"
    monkeypatch.setattr(lineage_module, "get_lineage_log_path", lambda: log_path)
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX", {})
    monkeypatch.setattr(lineage_module, "_LINEAGE_INDEX_LOADED", False)

    execution_id = "phase6-tampered-replay"
    append_lineage_event(execution_id, "CREATED", "hash-a", "runtime", details={"artifact_dir": str(phase6_artifact_dir)})
    append_lineage_event(execution_id, "APPROVED", "hash-a", "runtime", details={"artifact_dir": str(phase6_artifact_dir)})

    _tamper_lineage_record(log_path, execution_id)

    with pytest.raises(PayloadHashMismatchError):
        replay_execution_lineage(execution_id)