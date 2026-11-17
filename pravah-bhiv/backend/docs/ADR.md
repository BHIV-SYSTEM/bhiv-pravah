# ARCHITECTURE DECISION RECORD (ADR)
## ADR-001: Deterministic Stream Processor & Append-Only Replay Ledger (v1.0)

- **Status**: ACCEPTED / IMPLEMENTED
- **Date**: 2026-11-17
- **Author**: Kavy Changela (Senior Backend Engineer & Systems Architect)
- **Component**: PRAVAH Stream Processor & Replay Ledger Subsystem
- **Scope**: `pravah-bhiv/backend/pravah/` & `pravah-bhiv/backend/contracts/`

---

## 1. Context & Problem Statement

PRAVAH functions as the deterministic replay, observability, and cryptographic evidence ledger for the BHIV autonomous ecosystem. The system receives high-throughput event streams from microservices, orchestrators, and AI agents. 

Prior to this implementation:
1. Stream ingestion in `pravah_stream/stream.py` functioned solely as an in-memory buffer without strict schema enforcement or deterministic state reduction.
2. The persistence layer (`AppendOnlyLog` and `HashLineageVerifier`) supported low-level journal appending and verification, but lacked a cohesive, high-level `StreamProcessor` and unified `ReplayLedger` interface to process event sequences deterministically and record verified replay evidence.
3. Schema validation was fragmented across JSON schema files (`signal_schema.json`) and ad-hoc integration helpers, lacking strict Schema v1.0 validation on both inbound signals and outbound processed events with structured error reporting.

To satisfy the engineering requirements of **Task T-OUT-OF-SYLLABUS**, a unified, deterministic, and cryptographically verified Stream Processor and Replay Ledger must be integrated into the existing PRAVAH codebase without altering established contracts or breaking existing subsystems.

---

## 2. Existing Architecture Analysis

A thorough audit of the `pravah-bhiv/` codebase revealed the following foundations:
- **`control_plane/persistence/append_only_log.py`**: Provides `AppendOnlyLog`, managing an immutable append-only JSON Lines journal (`append_only_log.jsonl`) enforcing monotonic sequence numbers, previous hash linkage, and SHA-256 lineage proofs.
- **`control_plane/persistence/hash_lineage_verifier.py`**: Provides `HashLineageVerifier` verifying sequence continuity, chain integrity, and computing state hashes.
- **`control_plane/persistence/replay_index.py`**: Provides `ReplayIndex` and `SnapshotRegistry` for O(1) state lookups and checkpointing.
- **`contracts/semantic_transition_validator.py`**: Defines valid lifecycle states (`CREATED`, `APPROVED`, `EXECUTED`, `COMPLETED`, `FAILED`) and prevents invalid semantic skips.
- **`contracts/execution_contract.py`**: Enforces immutable execution contracts with Pydantic v2 models.
- **`schemas/signal_schema.json`**: Outlines canonical signal properties (`trace_id`, `execution_id`, `timestamp`, `source`, `signal_type`, `payload`).

---

## 3. Decision & Architecture Design

### A. Strict Schema v1.0 Validation
We implement `SchemaValidatorV1` in `pravah/schema_validator.py` using Pydantic v2 (pinned to `pydantic==2.13.3`):
- **Version Enforcement**: Payloads must specify `"schema_version": "1.0"`. Any missing or mismatched version is rejected immediately with code `UNSUPPORTED_SCHEMA_VERSION`.
- **Inbound Signal Validation**: Validates `trace_id`, `execution_id`, `timestamp` (ISO 8601), `source`, `signal_type` (`execution`, `verification`, `telemetry`, `action_request`), and non-empty `payload`.
- **Outbound Event Validation**: Validates processed result structure containing `execution_id`, `state`, `sequence`, `event_hash`, `state_hash`, `schema_version: "1.0"`, and `timestamp`.
- **Structured Error Model**: Errors return a standardized `ValidationErrorResponse` containing:
  - `valid`: `False`
  - `error_code`: Enum string (`UNSUPPORTED_SCHEMA_VERSION`, `MISSING_REQUIRED_FIELD`, `INVALID_DATA_TYPE`, `MALFORMED_PAYLOAD`, `INVALID_TIMESTAMP`)
  - `message`: Human-readable summary
  - `errors`: List of specific field-level diagnostic dicts (`{"loc": [...], "msg": "...", "type": "..."}`)

### B. Deterministic Stream Processor
We implement `StreamProcessor` in `pravah/stream_processor.py`:
- **State Transition Model**: FSM strictly follows PRAVAH semantic guidelines:
  `CREATED` → `APPROVED` → `EXECUTED` → `COMPLETED`
  Terminal states `COMPLETED` and `FAILED` are immutable (lock transitions).
  Prerequisites are enforced using `validate_semantic_transition`.
- **Deterministic State Reduction**:
  Given identical initial states and identical event streams, the processor produces byte-for-byte identical state representations.
- **Canonical Serialization**:
  All hashing uses canonical JSON serialization (`json.dumps(obj, sort_keys=True, separators=(',', ':'))`) encoded in UTF-8.
- **Zero Uncontrolled Randomness**:
  Timestamps are either preserved from deterministic inputs or monotonically indexed. No wall-clock randomness affects state hash generation.
- **State Fingerprint (`state_hash`)**:
  Calculated as `SHA256(H_1 + H_2 + ... + H_n)` over the ordered sequence of event hashes, matching `HashLineageVerifier.compute_execution_state_hash()`.

### C. Append-Only Replay Evidence Ledger
We implement `ReplayLedger` in `pravah/replay_ledger.py`:
- **Integration with `AppendOnlyLog`**:
  Wraps the verified `AppendOnlyLog` engine. Every processed stream event is committed as an immutable journal entry.
- **No Mutation Guarantee**:
  The journal file is strictly opened in append mode (`'a'`). Updates and deletes are impossible at the API level.
- **Cryptographic Hash Chain**:
  Each entry includes `sequence`, `execution_id`, `event_id`, `state`, `event_hash`, `previous_hash`, `sequence_hash`, and `lineage_proof`.
- **Replay Verification**:
  Provides `verify_replay(execution_id)` which reads the journal, runs `HashLineageVerifier`, and returns verification proof (`VALID`, `CHAIN_BREAK`, `SEQUENCE_BREAK`, etc.).

### D. Robust Exception Handling
- All public methods validate inputs prior to state mutation.
- Malformed inputs, illegal transitions, and hash breaks raise structured exceptions (`SchemaValidationError`, `SemanticTransitionError`, `ReplayLedgerError`).
- Unhandled exceptions are prevented through boundary wrappers that record failed states rather than crashing the processor.
- Logs and error outputs are sanitized; internal tokens and secrets are never reflected.

---

## 4. Consequences & Trade-offs

### Positive Consequences
- **Full Determinism**: Verified through automated 50-run SHA-256 test suite with 100% hash convergence.
- **Auditability**: Complete append-only evidence trail for every event processed.
- **Backward Compatibility**: Fully compatible with existing `pravah_stream` modules, `contracts/`, and `control_plane/persistence/`.
- **Pydantic v2 Compliance**: Utilizes existing modern Pydantic v2 features with zero deprecation warnings.

### Neutral / Addressed Trade-offs
- **Storage Growth**: Append-only ledgers grow monotonically. Addressed through indexed lookups (`ReplayIndex`) and checkpoint snapshots (`SnapshotRegistry`).
- **Strictness**: Non-1.0 schemas are rejected outright. This is intentional to prevent schema drift across ecosystem groups.

---

## 5. Verification Matrix

| Requirement | Implementation Mechanism | Test Suite |
| :--- | :--- | :--- |
| Schema v1.0 Validation | `SchemaValidatorV1` Pydantic models | `tests/test_pravah_schema_validation.py` |
| Deterministic Processing | `StreamProcessor.process_event()` | `tests/test_pravah_stream_processor.py` |
| Append-Only Ledger | `ReplayLedger.record_event()` | `tests/test_pravah_replay_ledger.py` |
| 50-Run SHA-256 Invariance | `scripts/verify_50_run_determinism.py` | Executable verification script |
| Error Boundary | Structured exceptions & fallbacks | `tests/test_pravah_error_handling.py` |
