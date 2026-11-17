# TASK PHASE 1.2: Pravah Persistence & Real Integration Forensics

## 1. Baseline
Execution Root: `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`
- **Tests Collected**: 216
- **Passed**: 216
- **Failed**: 0
- **Errors**: 0

The baseline remains exactly as established in the previous audit (flawlessly green).

## 2. Persistence Architecture & Requirements
A comprehensive scan of Pravah's documentation, architecture, and source code yields the following:
- **A. What state is Pravah responsible for?** Short-term bounded agent memory, execution lineage (append-only), capability discovery state, and trace logs.
- **B. What state belongs to external services?** Heavy canonical storage (e.g., PostGIS spatial data, raw observation ingestion) belongs to external components like VANA (Group 1 MasterDB).
- **C. Is database persistence required by an approved Pravah contract?** No. There is no architectural or contractual mandate within Pravah itself requiring a traditional relational database.
- **D. Is JSON/JSONL intentional?** Yes. `AgentMemory`, `ExecutionLineage`, and `AgentLogger` explicitly manage JSON/JSONL artifacts.
- **E. Is PostgreSQL/SQLite specified as a requirement?** No. PostgreSQL is exclusively mentioned in VANA integrations (Group 1 backend). 

**Classification**: Persistence Requirement is **PROVEN** to be local file storage natively.

## 3. Storage Failure Analysis
An audit of `ExecutionLineage` and `AgentLogger` yields the following failure behaviors:
- **Storage file/dir does not exist**: Handled correctly. Read returns empty state (Recovers). Write auto-creates directories.
- **File is truncated/malformed**: `_read_events()` wraps JSON decoding in a `try/except` and silently ignores corrupted lines (`continue`). This is a **FAILS OPEN** behavior for corrupted lineage reading (it drops the corrupted history but proceeds).
- **Write fails / Disk Full**: Handled via `os.fsync` and `handle.write()`. Uncaught IO errors will bubble up, causing the operation (or the agent process) to abort. This is a **FAILS CLOSED** behavior.
- **Concurrent Writes**: `ExecutionLineage` uses a thread lock (`_LINEAGE_LOCK`), ensuring thread safety *within* the process. However, cross-process concurrency relies purely on the OS.

## 4. Group 1 Real Integration Contract
The verified Group 1 service (`http://163.128.209.18:8013`) provides observation ingestion.
- **POST Schema**: Accepts canonical observations. Documented in VANA handovers.
- **Validation**: Enforced externally.
- **Authentication**: No HTTP-level authentication required for intra-cluster traffic.
- **Retrieval**: `GET /observations/{observation_id}`.

## 5. Determine Whether Safe Live POST is Possible
A repository-wide inspection for a sandbox or test POST endpoint yields **no officially documented safe staging endpoint** for Group 1 ingestion. No idempotency token or dry-run flag is documented for the live POST contract. 
Given the absence of a documented sandbox, a POST cannot be safely executed against the live cluster without mutating real external data.

**Live POST Integration**: **NOT PROVEN** (because no safe mechanism is documented, and Pravah tests do not execute it).

## 6. Pravah → Group 1 Path
A rigorous search through the codebase reveals that while Pravah contains the registry metadata for Group 1, there is **zero production code** inside Pravah that actually dynamically constructs or executes a `POST /observations` request using the `CapabilityDiscovery` output. 
The actual invocation of the Group 1 capability from within Pravah is **NOT IMPLEMENTED / NOT PROVEN**.

## 7. Executor / Governance E2E Boundary
Pravah's test suite heavily relies on mocks for external boundaries:
- **Mocked ActionGovernance**: Patched heavily in `test_phase8_execution_closure.py` and Phase 15 tests.
- **Mocked HTTP boundaries**: `requests.post` is systematically patched across all integration layers.
- **Mocked Security**: `sign_trace` and `canonicalize` are bypassed in execution closure tests.

**Classification**: The executor/governance boundary E2E integration is **MOCKED**.

## 8. Observability at Real Boundaries
If a boundary fails (e.g., `SafeOrchestrator` encountering an unavailable executor), it catches the exception and logs an error status. The lineage verifier correctly captures the trace identifiers and signatures of these rejected paths. 
Because the E2E boundary is mocked, the true fidelity of these logs during a live network failure (e.g., Group 1 timeout) remains theoretical, though the internal architecture supports it properly.

## 9. Error Handling
- **Input Failure**: Throws/returns error → Handled by `AgentRuntime` catching the exception → Logs error → Agent state transition to idle (FAILS CLOSED).
- **Execution Refusal**: `ActionGovernance` defaults to `NOOP`/`GAP` abstentions, safely logging the refusal (FAILS CLOSED).
- **Missing Capabilities**: `ExecutionRightsAdapter` explicitly rejects unmapped capabilities (FAILS CLOSED).
There are no major fail-open paths for governance routing, ensuring the agent remains safely contained.

## 10. Phase 1 Gap Matrix

| Requirement | Evidence | Implementation | Test | Real Runtime Evidence | Status | Gap |
|---|---|---|---|---|---|---|
| SOURCE CODE | `agent_runtime.py` | Native | Mocks E2E | App logs | PROVEN | None |
| API CONTRACTS | `execution_rights_adapter` | Enforced | Unit Tests | Trace logs | PROVEN | None |
| PERSISTENCE | JSON/JSONL | Local File I/O | Unit Tests | JSON files | PARTIALLY PROVEN | Silent fail-open read on corrupted lines |
| STORAGE INTEGRITY | `lineage_verifier.py` | HMAC hashes | Unit Tests | Local files | PROVEN | None |
| RECOVERY | Replay semantics | Native | Adv. Tests | None | PROVEN | None |
| GROUP1 INTEGRATION | No POST code in Pravah | Missing | None | curl health | NOT PROVEN | Pravah implementation absent |
| EXECUTOR INTEGRATION| `executor.py` | HTTP | Mocks | None | PARTIALLY PROVEN | Relies exclusively on `mock_post` |
| OBSERVABILITY | `agent_logger.py` | Native | Unit Tests | Lineage logs | PROVEN | None |
| ERROR HANDLING | Fail-Closed Bounds | Enforced | Unit Tests | Refusal logs | PROVEN | None |
| SECURITY | Signed traces | Native | Unit Tests | Log signatures | PROVEN | None |
| E2E QUALITY | Patches/Mocks | Mocks | Pytest | None | PARTIALLY PROVEN | Unmocked E2E is missing |

## 11. Recommended Remediation Order
1. **Develop actual Pravah implementation for Group 1 capability execution**: Build the network path that fetches `http://163.128.209.18:8013` from the registry and issues a real HTTP POST.
2. **Remove Mocks**: Refactor tests (Phase 8/15) to run against local test servers rather than `unittest.mock.patch` for `requests.post` and `ActionGovernance`.
3. **Patch Persistence Fail-Open**: Update `_read_events()` in `execution_lineage.py` to handle `JSONDecodeError` aggressively rather than silently ignoring corrupted lineage items.

## 12. Final Classification
Given that true endpoint communication logic is missing for Group 1, and core E2E flows are heavily mocked in the test suite:

**PHASE 1 PARTIALLY VERIFIED**

*Note: 216/216 passing tests unequivocally proves the unit and component logic is healthy, but it does not equate to "real E2E validation", nor "Phase 1 Completion", nor "production readiness."*
