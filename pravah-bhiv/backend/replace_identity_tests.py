"""
Replace tests 16-onward in test_phase15_gap_governed_abstention.py
with the corrected 9-test identity model suite.
"""
import pathlib

f = pathlib.Path(__file__).parent / "tests" / "test_phase15_gap_governed_abstention.py"
lines = f.read_text(encoding="utf-8").splitlines(keepends=True)

# Keep everything up to line 458 (0-indexed), i.e. the blank line after test 15's last line
kept = "".join(lines[:458])

new_section = (
    "\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Helper: pre-built approved GovernanceDecision for recorder-focused tests.\n"
    "# Governance admission is proven by test_governance_allows_noop_contract.\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "def _approved_decision():\n"
    '    return GovernanceDecision(\n'
    '        should_block=False,\n'
    '        policy_id="action_governance_v1",\n'
    '        policy_version="v1",\n'
    '        admission_state="POLICY_ADMITTED",\n'
    '    )\n'
    "\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Test 16 (Required Test 1) - Same inputs -> same abstention_record_id\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "def test_abstention_record_id_same_inputs_same_id(adapter, authoritative_ruling, tmp_path):\n"
    '    """Required Test 1: Same observation_id + context_id + ruling -> same abstention_record_id."""\n'
    "    contract = adapter.translate(authoritative_ruling)\n"
    "    approved = _approved_decision()\n"
    '    log_path = str(tmp_path / "t1.jsonl")\n'
    "    ev1 = GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)\n"
    "    ev2 = GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)\n"
    '    assert ev1["abstention_record_id"] == ev2["abstention_record_id"], "Same inputs must produce same abstention_record_id"\n'
    '    assert ev1["abstention_record_id"].startswith("abstention-")\n'
    "\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Test 17 (Required Test 2) - Different execution_id -> same abstention_record_id\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "def test_abstention_record_id_independent_of_execution_id(adapter, tmp_path):\n"
    '    """\n'
    "    Required Test 2: Same observation_id + context_id + ruling but different execution_id\n"
    "    -> same abstention_record_id. execution_id is runtime-owned and excluded from derivation.\n"
    '    """\n'
    "    base = {\n"
    '        "contract_version": "group2.temporal-applicability.v1",\n'
    '        "observation_id": "TC-Z03-F02-LIDAR-OBS001",\n'
    '        "context_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",\n'
    '        "ruling": "GAP",\n'
    '        "action_eligibility": False,\n'
    '        "abstention_required": True,\n'
    '        "authority": "Group 2 Temporal Applicability",\n'
    "    }\n"
    '    ca = adapter.translate({**base, "execution_id": "exec-vana-environmental_observation-9e011c64"})\n'
    '    cb = adapter.translate({**base, "execution_id": "exec-vana-environmental_observation-DIFFERENT"})\n'
    "    approved = _approved_decision()\n"
    '    log_path = str(tmp_path / "t2.jsonl")\n'
    "    eva = GovernedAbstentionRecorder(log_path=log_path).record(contract=ca, governance_decision=approved)\n"
    "    evb = GovernedAbstentionRecorder(log_path=log_path).record(contract=cb, governance_decision=approved)\n"
    '    assert eva["abstention_record_id"] == evb["abstention_record_id"], (\n'
    '        "Different execution_id must NOT change abstention_record_id"\n'
    "    )\n"
    "\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Test 18 (Required Test 3) - Different trace_id -> same abstention_record_id\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "def test_abstention_record_id_independent_of_trace_id(adapter, tmp_path):\n"
    '    """\n'
    "    Required Test 3: Same observation_id + context_id + ruling but different trace_id\n"
    "    -> same abstention_record_id. trace_id is request-owned and excluded from derivation.\n"
    '    """\n'
    "    base = {\n"
    '        "contract_version": "group2.temporal-applicability.v1",\n'
    '        "observation_id": "TC-Z03-F02-LIDAR-OBS001",\n'
    '        "context_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",\n'
    '        "ruling": "GAP",\n'
    '        "action_eligibility": False,\n'
    '        "abstention_required": True,\n'
    '        "authority": "Group 2 Temporal Applicability",\n'
    "    }\n"
    '    ca = adapter.translate({**base, "trace_id": "trace-vana-a608b5abbd94d931"})\n'
    '    cb = adapter.translate({**base, "trace_id": "trace-vana-COMPLETELY-DIFFERENT"})\n'
    "    approved = _approved_decision()\n"
    '    log_path = str(tmp_path / "t3.jsonl")\n'
    "    eva = GovernedAbstentionRecorder(log_path=log_path).record(contract=ca, governance_decision=approved)\n"
    "    evb = GovernedAbstentionRecorder(log_path=log_path).record(contract=cb, governance_decision=approved)\n"
    '    assert eva["abstention_record_id"] == evb["abstention_record_id"], (\n'
    '        "Different trace_id must NOT change abstention_record_id"\n'
    "    )\n"
    "\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Test 19 (Required Test 4) - Replay: same abstention_record_id, different event_id\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "def test_replay_same_abstention_record_id_different_event_id(adapter, authoritative_ruling, tmp_path):\n"
    '    """\n'
    "    Required Test 4: Replay the same abstention twice.\n"
    "    abstention_record_id = SAME (deterministic, stable)\n"
    "    event_id             = DIFFERENT (unique per ledger write)\n"
    '    """\n'
    "    contract = adapter.translate(authoritative_ruling)\n"
    "    approved = _approved_decision()\n"
    '    log_path = str(tmp_path / "t4.jsonl")\n'
    "    ev1 = GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)\n"
    "    ev2 = GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)\n"
    '    assert ev1["abstention_record_id"] == ev2["abstention_record_id"], "abstention_record_id must be stable across replays"\n'
    '    assert ev1["event_id"] != ev2["event_id"], "Each ledger write must produce a unique event_id"\n'
    "\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Test 20 (Required Test 5) - execution_id and trace_id preserved on ledger event\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "def test_execution_and_trace_id_preserved_on_ledger_event(adapter, tmp_path):\n"
    '    """\n'
    "    Required Test 5: execution_id and trace_id are NOT used in abstention_record_id\n"
    "    derivation, but MUST still be present on the recorded ledger event.\n"
    '    """\n'
    "    import json as _json\n"
    "    ruling_with_ids = {\n"
    '        "contract_version": "group2.temporal-applicability.v1",\n'
    '        "observation_id": "TC-Z03-F02-LIDAR-OBS001",\n'
    '        "context_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",\n'
    '        "ruling": "GAP",\n'
    '        "action_eligibility": False,\n'
    '        "abstention_required": True,\n'
    '        "authority": "Group 2 Temporal Applicability",\n'
    '        "trace_id": "trace-vana-a608b5abbd94d931",\n'
    '        "execution_id": "exec-vana-environmental_observation-9e011c64",\n'
    "    }\n"
    "    contract = adapter.translate(ruling_with_ids)\n"
    "    approved = _approved_decision()\n"
    '    log_path = str(tmp_path / "t5.jsonl")\n'
    "    GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)\n"
    "    lines = Path(log_path).read_text(encoding='utf-8').strip().splitlines()\n"
    "    event_details = _json.loads(lines[0])['event']['details']\n"
    '    assert event_details["trace_id"] == "trace-vana-a608b5abbd94d931", "trace_id must be on the ledger event"\n'
    '    assert event_details["execution_id"] == "exec-vana-environmental_observation-9e011c64", "execution_id must be on the ledger event"\n'
    "\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Test 21 (Required Test 6) - Adapter and recorder work without optional fields\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "def test_adapter_and_recorder_work_without_optional_provenance_fields(adapter, tmp_path):\n"
    '    """\n'
    "    Required Test 6: Adapter and recorder work when trace_id and execution_id are absent.\n"
    "    abstention_record_id is computable because it derives only from\n"
    "    observation_id, context_id, and ruling.\n"
    '    """\n'
    "    minimal_ruling = {\n"
    '        "contract_version": "group2.temporal-applicability.v1",\n'
    '        "observation_id": "TC-Z03-F02-LIDAR-OBS001",\n'
    '        "context_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",\n'
    '        "ruling": "GAP",\n'
    '        "action_eligibility": False,\n'
    '        "abstention_required": True,\n'
    '        "authority": "Group 2 Temporal Applicability",\n'
    "    }\n"
    "    contract = adapter.translate(minimal_ruling)\n"
    '    assert contract.action == "noop"\n'
    '    assert contract.decision_type == "abstention"\n'
    "    assert contract.parameters.get('trace_id') is None\n"
    "    assert contract.parameters.get('execution_id') is None\n"
    "    approved = _approved_decision()\n"
    '    log_path = str(tmp_path / "t6.jsonl")\n'
    "    evidence = GovernedAbstentionRecorder(log_path=log_path).record(contract=contract, governance_decision=approved)\n"
    '    assert evidence["abstention_record_id"].startswith("abstention-")\n'
    '    assert evidence["observation_id"] == "TC-Z03-F02-LIDAR-OBS001"\n'
    '    assert evidence["context_id"] == "f47ac10b-58cc-4372-a567-0e02b2c3d479"\n'
    "\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Test 22 (Required Test 7) - Changing observation_id changes abstention_record_id\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "def test_different_observation_id_changes_abstention_record_id():\n"
    '    """Required Test 7: Changing observation_id must produce a different abstention_record_id."""\n'
    "    id_a = GovernedAbstentionRecorder._compute_abstention_record_id(\n"
    '        observation_id="TC-Z03-F02-LIDAR-OBS001",\n'
    '        context_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",\n'
    '        ruling="GAP",\n'
    "    )\n"
    "    id_b = GovernedAbstentionRecorder._compute_abstention_record_id(\n"
    '        observation_id="TC-Z03-F02-LIDAR-OBS002",\n'
    '        context_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",\n'
    '        ruling="GAP",\n'
    "    )\n"
    '    assert id_a != id_b, "Different observation_id must produce a different abstention_record_id"\n'
    "\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Test 23 (Required Test 8) - Changing context_id changes abstention_record_id\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "def test_different_context_id_changes_abstention_record_id():\n"
    '    """Required Test 8: Changing context_id must produce a different abstention_record_id."""\n'
    "    id_a = GovernedAbstentionRecorder._compute_abstention_record_id(\n"
    '        observation_id="TC-Z03-F02-LIDAR-OBS001",\n'
    '        context_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",\n'
    '        ruling="GAP",\n'
    "    )\n"
    "    id_b = GovernedAbstentionRecorder._compute_abstention_record_id(\n"
    '        observation_id="TC-Z03-F02-LIDAR-OBS001",\n'
    '        context_id="00000000-0000-0000-0000-000000000000",\n'
    '        ruling="GAP",\n'
    "    )\n"
    '    assert id_a != id_b, "Different context_id must produce a different abstention_record_id"\n'
    "\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Test 24 (Required Test 9) - Changing ruling changes abstention_record_id\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "def test_different_ruling_changes_abstention_record_id():\n"
    '    """Required Test 9: Changing ruling must produce a different abstention_record_id."""\n'
    "    id_gap = GovernedAbstentionRecorder._compute_abstention_record_id(\n"
    '        observation_id="TC-Z03-F02-LIDAR-OBS001",\n'
    '        context_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",\n'
    '        ruling="GAP",\n'
    "    )\n"
    "    id_adapt = GovernedAbstentionRecorder._compute_abstention_record_id(\n"
    '        observation_id="TC-Z03-F02-LIDAR-OBS001",\n'
    '        context_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",\n'
    '        ruling="ADAPT",\n'
    "    )\n"
    '    assert id_gap != id_adapt, "Different ruling must produce a different abstention_record_id"\n'
    "\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Test 25 - V2.2 timestamp conflict documented as known open item\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "def test_v22_timestamp_conflict_is_known_open_item():\n"
    '    """\n'
    "    KNOWN CONFLICT: Group 2 ruling reason says timestamp unavailable,\n"
    "    but Group 3 V2.2 has observation_timestamp=2026-08-13T09:14:22Z.\n"
    "    V2.2 observation is outside context window (ends 2023-12-31).\n"
    "    Per Kaushal's decision table: ruling outcome remains GAP.\n"
    "    Abstention flow is NOT removed. Governance outcome is NOT changed.\n"
    "    Only the reason string needs updating by Group 2.\n"
    '    """\n'
    "    import json as _json\n"
    "    from pathlib import Path as _Path\n"
    "    from datetime import datetime as _dt\n"
    "    ruling_path = (\n"
    '        _Path(__file__).resolve().parents[1] / "integration" / "group2" / "temporal_applicability_ruling.json"\n'
    "    )\n"
    '    assert ruling_path.exists(), "Group 2 ruling artifact must be committed"\n'
    "    ruling = _json.loads(ruling_path.read_text(encoding='utf-8'))\n"
    "    assert ruling['source_reference_time'] is None\n"
    "    assert ruling['temporal_relationship'] == 'UNAVAILABLE'\n"
    '    V22_OBS_TS = "2026-08-13T09:14:22Z"\n'
    "    ctx_end = ruling['applicable_window']['end']\n"
    "    obs_dt = _dt.fromisoformat(V22_OBS_TS.replace('Z', '+00:00'))\n"
    "    ctx_end_dt = _dt.fromisoformat(ctx_end.replace('Z', '+00:00'))\n"
    '    assert obs_dt > ctx_end_dt, f"V2.2 obs ({V22_OBS_TS}) outside window ({ctx_end}) - Group 2 reason needs update"\n'
    "    # Confirm governance outcome stays GAP\n"
    "    assert ruling['ruling'] == 'GAP'\n"
    "    assert ruling['action_eligibility'] is False\n"
    "    assert ruling['abstention_required'] is True\n"
)

f.write_text(kept + new_section, encoding="utf-8")
total = len(f.read_text(encoding="utf-8").splitlines())
print(f"Done. Total lines: {total}")
