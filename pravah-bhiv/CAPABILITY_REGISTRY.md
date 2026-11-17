# Capability Registry

## 1. Purpose
The Capability Registry serves as the ground-truth inventory of runtime capabilities across all groups. It explicitly captures the difference between known implementations, documented contracts, and active live services to prevent false integration assumptions.

## 2. Registry Design
The registry uses a unified discovery mechanism that reconciles legacy `.json` registry applications with new capability definitions. It maps components explicitly by their `capability_id`, `owner.group`, and `capability_type`.

## 3. Capability Inventory
| Capability ID | Type | Owner | Maturity | Status |
|---------------|------|-------|----------|--------|
| `group3-field-edge` | `edge_robotics` | Group 3 | V1 | DOCUMENTED |
| `group1-observation-api` | `observation_ingestion` | Group 1 | V1 | DOCUMENTED |
| `group2-scientific-context` | `context_resolution` | Group 2 | V1 | BLOCKED |
| `governed-execution` | `governed_execution` | Group 4 | V1 | PRESENT |
| `svacs-runtime` | `runtime_dependency` | Unverified | UNKNOWN | BLOCKED |
| `bucket-evidence` | `evidence_store` | Group 4 | V1 | BLOCKED |
| `replay-runtime` | `replay` | Group 4 | V1 | PRESENT |

## 4. Status Semantics
- **PRESENT**: Implementation exists, but is not an active service.
- **DOCUMENTED**: Contract/capability documented (e.g. locally verified but pending deployment).
- **BLOCKED**: Capability known but required runtime/integration dependency is unavailable.
- **LIVE/ACTIVE**: Actively hosted and reachable endpoint (Currently none).

## 5. Discovery Mechanism
Capabilities are dynamically resolved by `MultiAppControlPlane.list_runtime_entities()` and queried using `CapabilityDiscovery` filtering (`discover_by_type`, `discover_by_status`, `discover_by_group`).

## 6. Cross-Group Dependency Mapping
| Flow | Capability | Owner | Input | Output | Runtime Status | Blocker |
|------|------------|-------|-------|--------|----------------|---------|
| Group 3 → Group 1 | `group3-field-edge` | Group 3 | Controlled observation | Mission package | DOCUMENTED | No live device/service |
| Group 1 | `group1-observation-api` | Group 1 | Observation | Canonical record | DOCUMENTED | VM deployment pending |
| Group 2 | `group2-scientific-context` | Group 2 | Canonical observation | Context result | BLOCKED | Local/not live |
| Group 4 | `governed-execution` | Group 4 | Action request | Governed execution | PRESENT | HTTP/runtime contract unresolved |
| Group 4 dependency | `svacs-runtime` | Unverified | Runtime dependency | Unknown | BLOCKED | Owner/source/endpoint unresolved |
| Group 4 | `bucket-evidence` | Group 4 ecosystem | Execution/trace | Evidence artifact | BLOCKED | Remote endpoint unavailable |
| Group 4 | `replay-runtime` | Group 4 | Evidence/trace | Replay result | PRESENT | Shared runtime integration not yet proven |

## Endpoint / Owner Matrix
*Note: `endpoint: null` does not necessarily mean missing data. Some capabilities are intentionally not service-hosted.*

| Capability | Owner | Endpoint | Reason |
|------------|-------|----------|--------|
| `group3-field-edge` | Group 3 | `null` | Mission package producer, not a hosted service |
| `group1-observation-api` | Group 1 | `null` | VM deployment pending |
| `group2-scientific-context` | Group 2 | `null` | Automation blocked, local script only |
| `governed-execution` | Group 4 | `null` | Internal modules present; no HTTP entrypoint verified |
| `svacs-runtime` | Unverified | `null` | Endpoint and owner unresolved/unreachable |
| `bucket-evidence` | Group 4 | `null` | Remote endpoint is HTTP 503 / ephemeral |
| `replay-runtime` | Group 4 | `null` | Runtime endpoint not verified |

## 7. Execution Rights Compatibility
**Status: PARTIAL / ADAPTER REQUIRED**

The Capability Registry and the existing Execution Rights/Constitutional Boundary System do not conflict, but they operate on distinct identifiers (Capability Registry uses `capability_id`/`owner`, while Execution Rights uses `source_id` strings and core engine roles). There is no automatic runtime mapping.

## 8. Known Runtime Limitations
- No live endpoint available for end-to-end integration.
- Group 2 context resolution currently yields `GAP` for critical inputs like `canopy_height`.
- SVACS ownership and implementation are phantom dependencies.

## 9. Registration/Retrieval Evidence
Verified via `test_capability_discovery.py` discovering all 7 mapped capabilities accurately without hallucinating active endpoints.
