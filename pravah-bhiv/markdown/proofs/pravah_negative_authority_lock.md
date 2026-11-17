# Pravah Negative Authority Lock (Phase 8)

This document establishes the hard negative authority locks and boundaries of the **Pravah Control Plane** to ensure the runtime remains an enforcement and observation engine, never acquiring sovereignty.

---

## 1. Allowed System Operations (Pravah MAY)

The Pravah control plane is programmatically authorized to perform only the following operations:
1. **Persist Lineage**: Pravah MAY append immutable events to the journal [AppendOnlyLog](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/persistence/append_only_log.py#L60) upon valid execution state advances.
2. **Reconstruct States**: Pravah MAY load execution histories from disk and rebuild indexes/snapshots programmatically in [RecoveryValidator](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/deployment/recovery_validator.py#L30) during restart validation.
3. **Observe Signals**: Pravah MAY monitor metrics and status events flowing through the observability stream [monitor/app.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/reliability-controller2-main/monitor/app.py).
4. **Surface Runtime State**: Pravah MAY display logs and statuses via dashboard panels.
5. **Preserve Lineage Integrity**: Pravah MAY verify cryptographic lineages using [HashLineageVerifier](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/persistence/hash_lineage_verifier.py) to confirm transition validity.

---

## 2. Hard Negative Authority Prohibitions (Pravah MAY NOT)

To prevent the runtime from silently acquiring sovereign authority, the following actions are strictly and permanently prohibited:
1. **Pravah SHALL NOT manufacture authority**: The control plane has zero authority to bypass, expand, or rewrite its active runtime security policies. Authority is derived strictly and exclusively from GC-approved signed governance artifacts.
2. **Pravah SHALL NOT reinterpret legitimacy**: Pravah cannot alter, relax, or re-classify legitimacy definitions or validation states (`LEGITIMATE_VALID`, `LEGITIMATE_DEGRADED`, `LEGITIMATE_AMBIGUOUS`, `ILLEGITIMATE`).
3. **Pravah SHALL NOT rewrite canonical semantics**: Pravah cannot alter execution schemas, transition sequences, or semantic prerequisites defined in [SemanticGuardEngine](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/control_plane/security/semantic_guard_engine.py#L155).
4. **Pravah SHALL NOT silently authorize degraded continuation**: In the event of dependency connection losses, the system must immediately and transparently report degraded modes. Bypassing or hiding connection failures is strictly forbidden.
5. **Pravah SHALL NOT inherit orchestration sovereignty**: Pravah is an enforcement agent. It does not own or modify the constitutional source of truth.
6. **Pravah SHALL NOT own governance semantics**: Operational rules and policy parameters reside permanently outside the runtime's authority bounds.

---

## 3. Sovereignty Lock & Boundary Definitions

* **Governance Authority**: Resides permanently with external, GC-approved signed policies.
* **Legitimacy Authority**: Defined exclusively by the constitution and runtime doctrine.
* **Replay Authority**: Read-only validation layer. No state updates or structural overrides are permitted during replay.
* **Enforcement Bound**: Programmatic compliance checking. Pravah cannot bypass or override validation constraints.
