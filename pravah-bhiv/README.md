# PRAVAH — Stream Processor Logic & Append-Only Evidence Ledger

## Overview
PRAVAH is the deterministic event streaming, replay verification, and cryptographic evidence ledger for the BHIV autonomous system ecosystem.

This repository hosts the PRAVAH stream processing engine, schema enforcement interfaces (Schema v1.0), and cryptographic replay ledger.

---

## Architecture Summary
- **Schema Validation Layer (`pravah.schema_validator`)**:
  - Enforces Schema Version 1.0 on all inbound signals and outbound events.
  - Returns structured, actionable validation error models (`ValidationResult`, `ValidationErrorDetail`, `ValidationErrorCode`).
  - Fail-closed design prevents malformed or unversioned events from contaminating downstream processors.
- **Append-Only Replay Ledger (`pravah.replay_ledger`)**:
  - Encapsulates `AppendOnlyLog`, `HashLineageVerifier`, and `ReplayIndex`.
  - Enforces SHA-256 hash-chain linkage (`event_hash`, `previous_hash`, `lineage_proof`).
  - Immutability guarantee: journal files are append-only (`'a'`); records are never updated or deleted.
- **Deterministic Stream Processor (`pravah.stream_processor`)**:
  - Enforces legal FSM state transitions: `CREATED` → `APPROVED` → `EXECUTED` → `COMPLETED` (or terminal `FAILED`).
  - Validates semantic prerequisites via `contracts/semantic_transition_validator.py`.
  - Generates cumulative deterministic state fingerprints (`state_hash`).
  - Zero uncontrolled randomness or wall-clock drift.

---

## Directory Structure
```
bhiv-pravah/
├── docs/
│   └── ADR.md                                 # Architecture Decision Record
├── review_packets/
│   ├── REVIEW_PACKET.md                       # Comprehensive Engineering Review Packet
│   ├── Code_Packets/                          # Packaged source modules & test files
│   └── Evidence/                              # 50-run verification logs and proofs
└── pravah-bhiv/
    ├── backend/
    │   ├── contracts/                         # Pydantic v2 execution & runtime contracts
    │   ├── control_plane/persistence/         # Core append-only log, verifiers, indices
    │   ├── pravah/                            # Core Stream Processor, Replay Ledger & Validator
    │   │   ├── __init__.py
    │   │   ├── schema_validator.py
    │   │   ├── replay_ledger.py
    │   │   └── stream_processor.py
    │   ├── pravah_stream/                     # Stream primitives & compatibility exports
    │   ├── scripts/                           # Determinism verification scripts
    │   │   └── verify_50_run_determinism.py
    │   └── tests/                             # Comprehensive automated test suite
    │       ├── test_pravah_schema_validation.py
    │       ├── test_pravah_replay_ledger.py
    │       ├── test_pravah_stream_processor.py
    │       ├── test_pravah_error_handling.py
    │       ├── test_pravah_determinism_50_runs.py
    │       └── adversarial_test_suite/
    └── frontend/                              # Replay visualizer UI
```

---

## Verification & Execution Commands

### 1. Run Automated Test Suite
```powershell
cd pravah-bhiv/backend
$env:PYTHONPATH="."
python -m pytest tests/test_semantic_transition_validator.py `
                 tests/test_phase3_persistence_sovereignty.py `
                 tests/test_phase2_deterministic_policy_engine.py `
                 tests/test_replay_sovereignty.py `
                 tests/adversarial_test_suite `
                 tests/test_pravah_schema_validation.py `
                 tests/test_pravah_replay_ledger.py `
                 tests/test_pravah_stream_processor.py `
                 tests/test_pravah_error_handling.py `
                 tests/test_pravah_determinism_50_runs.py -v
```

### 2. Execute 50-Run SHA-256 Determinism Verification
```powershell
python pravah-bhiv/backend/scripts/verify_50_run_determinism.py
```

### 3. Verify Pinned Dependencies
```powershell
pip list | findstr "pydantic cryptography pytest"
```
Required and verified pins:
- `pydantic==2.13.3`
- `cryptography==49.0.0`
- `pytest==9.0.3`
- `pytest-asyncio==0.24.0`
