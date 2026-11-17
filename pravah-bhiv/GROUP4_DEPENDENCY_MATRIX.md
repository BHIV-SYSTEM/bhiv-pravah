# GROUP 4 DEPENDENCY MATRIX

This matrix tracks the state of cross-group and internal dependencies critical for the VANA integration and execution pipeline.

| Dependency Path | Registry Status | Runtime Status | Contract Status | Integration Status |
| :--- | :--- | :--- | :--- | :--- |
| **Group 3 → Group 1**<br>*(Mission Pkg → Observations)* | `DOCUMENTED` → `PRESENT` | `NOT_TESTED` → `LIVE` | **UNKNOWN CONTRACT**<br>*(Missing Schemas)* | **NOT INTEGRATED** |
| **Group 1 → Group 2**<br>*(Canonical Record → Context)* | `PRESENT` → `BLOCKED` | `LIVE` → `LOCAL_NOT_LIVE` | **UNKNOWN CONTRACT**<br>*(Missing Schemas)* | **NOT INTEGRATED** |
| **Group 2 → Governance**<br>*(Context → Decision Engine)* | `BLOCKED` → `PRESENT` | `LOCAL_NOT_LIVE` → `INTEGRATED` | **NO TRANSFORMATION CONTRACT EXISTS** | **MISSING REQUIRED ADAPTER / DECISION LAYER** |
| **Governance → Execution**<br>*(Decision Engine → Governed Exec)*| `PRESENT` → `PRESENT` | `INTEGRATED` → `INTEGRATED` | **COMPATIBLE**<br>*(ExecutionContract matches)* | **INTEGRATED** |
| **Execution → Bucket**<br>*(Execution Result → HTTP Evidence)*| `PRESENT` → `BLOCKED` | `INTEGRATED` → `UNAVAILABLE` | **UNKNOWN CONTRACT**<br>*(Missing HTTP PUT schema)* | **NOT INTEGRATED** |
| **Execution → Replay**<br>*(Execution Trace → Replay Runtime)*| `PRESENT` → `PRESENT` | `INTEGRATED` → `PRESENT` | **UNKNOWN CONTRACT**<br>*(Missing Replay schema)* | **NOT INTEGRATED** |

## Status Definitions
- **Registry Status**: Reflects the `status` field defined in the Capability Registry files.
- **Runtime Status**: Reflects the actual runtime health and metadata (`LIVE`, `BLOCKED`, `LOCAL_NOT_LIVE`, `UNAVAILABLE`).
- **Contract Status**: Reflects whether explicit Python/JSON schemas exist and are structurally compatible. Differentiates between missing schemas (`UNKNOWN CONTRACT`) and missing architectural transformations (`NO TRANSFORMATION CONTRACT EXISTS`).
- **Integration Status**: Reflects whether an actual code adapter exists and successfully bridges the two components. Differentiates between standard integration gaps (`NOT INTEGRATED`) and major architectural gaps (`MISSING REQUIRED ADAPTER / DECISION LAYER`).
