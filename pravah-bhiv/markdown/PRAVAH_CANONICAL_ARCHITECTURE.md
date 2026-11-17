# PRAVAH CANONICAL ARCHITECTURE

**Status:** Constitutional Reference Material
**Scope:** Pravah Converged System Architecture

This document establishes the official architectural boundaries, authority declarations, and schema disciplines for all Pravah control plane systems within this workspace. It serves as the constitutional baseline for engineering decisions, deployment configurations, and anti-drift validation.

---

## 1. Canonical Role
Pravah is the canonical autonomous control plane platform for multi-application environments. Its role is to execute a continuous operational cycle (**Sense → Validate → Decide → Enforce → Act → Observe → Explain**) across target systems. It acts as the coordinator of real-time telemetry, cryptographic action governance, reinforcement learning decisions, and operator dashboards, ensuring that no infrastructure modification is made without deterministic safety gates.

---

## 2. Upstream Dependencies
Pravah depends on the following upstream components:
* **Telemetry Providers:** Instrumented applications (such as [web1](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/reliability-controller2-main/web1/app.py) and [web2](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/reliability-controller2-main/web2/app.py)) that emit metrics (CPU, Memory, error rates, latencies).
* **Observability Stream:** The OTel-style monitor service ([monitor/app.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/reliability-controller2-main/monitor/app.py)) publishing real-time Server-Sent Events (SSE).
* **App Registry:** Central config lists defining managed deployments (e.g. `control_plane/config/apps_registry.json`).

*Dependency Rule:* Upstream systems may feed telemetry signals into Pravah but must never validate, enforce, or decide actions independently.

---

## 3. Downstream Participants
Pravah acts as the authority for:
* **The Action Executor:** The target service runners (e.g. Rayyan's [executer/app.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/reliability-controller2-main/executer/app.py)) that receive signed execution payloads.
* **Operator Visualizations:** Curated Dashboards ([unified-monitor-dashboard-main](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/unified-monitor-dashboard-main)) consuming decision metrics and timelines.
* **Lineage Replayers:** Analytical audit processes querying cryptographic execution states.

*Downstream Rule:* Downstream components consume output states but cannot modify active runtime environments or bypass enforcement policies.

---

## 4. Execution Boundary
The execution boundary begins when a validated telemetry payload is ingested at the control plane backend (`/control-plane/runtime-ingest`) and ends when a signed action is dispatched to and verified by the executer.
* **Inside the Execution Boundary:** State encoding, Q-learning updates, action guards, cooldown checks, HMAC signing, execution, and state lineage transition advances.
* **Outside the Execution Boundary:** View layouts, dashboard queries, metric pollers, and offline log ingestion.

*Boundary Rule:* Actions altering infrastructure state must pass through the execution boundary; direct execution via bypass triggers is strictly illegal.

---

## 5. Validation Boundary
Validation is a hard gate. Intake payloads must validate against [runtime_payload_schema.json](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/runtime_payload_schema.json) before crossing the execution boundary.
* Payload fields must match required types exactly (e.g. fractional floats for CPU/memory telemetry, trace UUIDs).
* Payloads violating schema validations are rejected immediately. Silent corrections or fallbacks are prohibited.

---

## 6. Authority Declaration
* **Pravah IS:** The central authority for runtime ingestion, reinforcement learning decision generation, cryptographic action signatures, policy governance checks, and lineage verification.
* **Pravah IS NOT:** A raw metric storage database, an OTel transport pipeline, or a generic website dashboard displaying unverified synthetic telemetry.

*Authority Rule:* Subsystems that determine action eligibility or check safety constraints reside inside Pravah's execution authority. Visualization-only elements hold zero authority.

---

## 7. Non-Authority Declaration
Pravah does not own:
* Raw network trace logging or OTel packet aggregation.
* Target system execution contexts (such as local OS, Docker, or Kubernetes clusters), which are owned by host engines.
* External caller authorization beyond verification of cryptographic request signatures.

---

## 8. Replay Boundary
Replay is strictly read-only and must never mutate system states, Q-tables, or database files.
* **Inside Replay Boundary:** Reading cryptographic journals (`trace_log.jsonl`), verifying state-history hash chains, and debugging logic transitions.
* **Outside Replay Boundary:** Writing new decisions, updating weights, or triggering docker/k8s actions.

---

## 9. Observability Boundary
Pravah aggregates observability data to present runtime states to operators, but it does not define log transport semantics.
* Observability data displayed on dashboards must match verified backend logs.
* Observability components cannot intercept or alter the flow of action execution.

---

## 10. Enforcement Interaction
Pravah interacts with the enforcement layer (e.g. Sarathi gating) to protect downstreams.
* Executors must reject any request that does not contain valid cryptographic signatures and expected headers.
* Cooldown managers must suppress decision actions for a minimum of 60 seconds (15s for local tests) to prevent cascade action storms.

---

## 11. Schema Discipline
All telemetry, decision, and execution payloads must adhere to strict schemas.
* Schema drift is prevented by forcing version checks (`v1` parameters).
* Telemetry inputs using fractional metrics (e.g., `0.95` CPU) must be scaled to percentages (`95.0`) at the engine border to match RL state encoders.

---

## 12. Hidden-State Disclosure
Pravah must operate transparently. Silent fallbacks are prohibited.
* Dashboards must disclose if data is live, cached, derived, or placeholder/demo.
* Disconnection of decision engines or databases must trigger immediate UI degradation alerts.

---

## 13. Deployment Model
Pravah deploys locally as a decoupled microservices topology:
1. **Control Plane API & Agent Loop:** [multi-agent-control-plane-main](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main) (Port `8000`).
2. **RL Decision Brain (Brain):** [pravah-integration.py-main](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/pravah-integration.py-main) (Port `8008` / persistent JSON Q-table).
3. **Observability Aggregator:** [reliability-controller2-main/monitor](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/reliability-controller2-main/monitor) (Port `5004` / SSE `/signals/stream`).
4. **Action Executor:** [reliability-controller2-main/executer](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/reliability-controller2-main/executer) (Port `5003` / HMAC signed execution boundary).
5. **Unified Dashboard Frontend:** [unified-monitor-dashboard-main](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/unified-monitor-dashboard-main) (Port `8050`).

---

## 14. Anti-Drift Protections
To maintain architectural integrity, all components must:
* Validate incoming schemas.
* Verify request signatures (HMAC SHA256).
* Enforce state prerequisites (Phase 4 Semantic Transition verification: `CREATED` -> `APPROVED` -> `EXECUTED` -> `COMPLETED`).
* Avoid hardcoding user-specific local filesystem paths (e.g. `C:\Users\spal4\...`).
* Disclose derived or placeholder status states.

---

## 15. Constitutional Definitions

### Pravah IS:
* A state-machine-driven autonomous DevOps control plane.
* A cryptographic ledger of execution lineage.
* An environment-aware reinforcement learning decision authority.
* An enforcer of deterministic cooldown gates.

### Pravah IS NOT:
* A generic dashboard for unvalidated metric displays.
* A mock data generator.
* A direct executor of unverified command lines.
* A state-free routing bridge.