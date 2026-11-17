from __future__ import annotations

import pytest

from control_plane.core.execution_lineage import replay_execution_lineage
from security.lineage_verifier import UnsignedReplayEventError

from .helpers import append_valid_lineage, read_jsonl_records, write_jsonl_records


def test_unsigned_events_are_rejected(monkeypatch, tmp_path, phase6_artifact_dir):
    log_path = tmp_path / "execution_lineage.jsonl"
    execution_id = "phase6-unsigned-event"

    append_valid_lineage(execution_id, log_path, monkeypatch, states=("CREATED", "APPROVED"))

    records = read_jsonl_records(log_path)
    records[1].pop("signature", None)
    write_jsonl_records(log_path, records)

    with pytest.raises(UnsignedReplayEventError):
        replay_execution_lineage(execution_id)