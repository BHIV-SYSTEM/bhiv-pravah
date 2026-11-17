# PHASE 2.5.4 — REMOVAL OF SYNTHETIC EXTERNAL-LINK RESOURCE TELEMETRY REMEDIATION AUDIT

**Scope**: PRAVAH ONLY  
**Date**: September 7, 2026  
**Execution Root**: `C:\Users\black\OneDrive\Desktop\Pravah\bhiv-pravah\pravah-bhiv`  
**Classification**: **A** — Fabricated external-link resource telemetry completely eliminated; unavailable telemetry explicitly represented as nullable (`None` / `null` / `"N/A"`); genuine runtime compute-node telemetry preserved intact.

---

## 1. EXECUTIVE SUMMARY

Phase 2.5.3 forensically proven that the Control Plane dashboard payload for externally ingested links (`_INGESTED_LINKS`) presented hardcoded synthetic resource telemetry:
- `cpu_percent = 15`
- `memory_percent = 30`

Because external repositories and public HTTP URLs have no Pravah host agent or cgroup monitoring container, attributing `15% CPU` and `30% Memory` to them constituted synthetic telemetry presentation.

In **Phase 2.5.4**, this defect has been completely resolved:
1. **Backend Contract**: `LiveDomainStatus` schema updated so `cpu_percent` and `memory_percent` are nullable (`Optional[float] = None`).
2. **Dashboard Payload**: For `_INGESTED_LINKS`, `cpu_percent` and `memory_percent` are set strictly to `None`. No substitution of `0`, `15`, `30`, `100`, or other fabricated values.
3. **Runtime Compute Nodes Preserved**: Active compute nodes (`INGESTED_RUNTIME_STATE`) retain their genuine numeric CPU and Memory percentages.
4. **Frontend Types**: `LiveProductionMonitoredService` updated to `cpu_percent: number | null` and `memory_percent: number | null`.
5. **Frontend Display**:
   - `frontend/src/app/runtime/page.tsx`: Explicitly checks for null/undefined; renders `<span className="text-muted-foreground font-mono">N/A</span>` instead of fake percentage numbers or misleading progress bars. Genuine compute nodes continue displaying numeric percentages and progress bars.
   - `frontend/src/app/page.tsx`: Filters `resourceData` so only nodes with actual telemetry are plotted in the Resource Utilization chart. Empty states display explicit fallback messages, and tooltips format unavailable values as `"N/A"`.
6. **Integrity & Validation**: Full test suite passes with **353 passed** (348 original + 5 new targeted regression tests). Frontend TypeScript validation passes with **0 errors**. `git diff -- VANA/` is completely empty.

---

## 2. ROOT CAUSE FORENSICS

### 2.1 Origin of the Defect
In `backend/control_plane/backend/app/main.py` (`_build_live_dashboard_payload()`), when iterating over `_INGESTED_LINKS` to construct the dashboard `monitored_services` cards:
```python
# OLD FLAWED IMPLEMENTATION:
monitored_list.append({
    "name": clean_name,
    "domain": link.replace("https://", "").replace("http://", "").split("/")[0],
    "url": link,
    "status": item.get("status", "CONNECTED"),
    "health_score": health_score,
    "response_time_ms": item.get("response_time_ms", 150),
    "cpu_percent": 15,          # <--- DEFECT: Fabricated telemetry
    "memory_percent": 30,       # <--- DEFECT: Fabricated telemetry
    "uptime_percent": item.get("uptime_percent", 99.9),
    "last_action": _RECENT_DECISIONS[0].selected_action if len(_RECENT_DECISIONS) else "noop",
    "errors_24h": item.get("errors_24h", 0),
})
```

### 2.2 Pydantic Schema Barrier
`LiveDomainStatus` in `backend/control_plane/backend/app/schemas.py` previously declared:
```python
cpu_percent: float
memory_percent: float
```
This rigid non-nullable type prevented the backend from legitimately expressing that resource telemetry was absent or unavailable for external URLs without triggering Pydantic schema validation failures.

### 2.3 Frontend Assumption
The frontend interface `LiveProductionMonitoredService` typed `cpu_percent: number; memory_percent: number;` and unconditionally rendered progress bars and `${item.cpu_percent}%` labels.

---

## 3. EXACT PRODUCTION FILES CHANGED

Only the 7 authorized files were created or modified:

| File | Type | Changes Made |
|---|---|---|
| `backend/control_plane/backend/app/schemas.py` | Production | Changed `cpu_percent` and `memory_percent` in `LiveDomainStatus` to `Optional[float] = None`. Preserved non-nullable compute contracts (`DecisionRequest`). |
| `backend/control_plane/backend/app/main.py` | Production | Changed lines 750–751 in `_build_live_dashboard_payload()`: replaced `15` and `30` with `None` for `_INGESTED_LINKS`. Preserved numeric metrics calculation for `INGESTED_RUNTIME_STATE`. |
| `frontend/src/types/index.ts` | Production | Updated `LiveProductionMonitoredService` fields to `cpu_percent: number \| null; memory_percent: number \| null;`. |
| `frontend/src/app/page.tsx` | Production | Filtered `resourceData` to services with actual resource metrics; added tooltip formatter displaying `"N/A"` for null metrics; rendered clean empty state message if no compute nodes exist. |
| `frontend/src/app/runtime/page.tsx` | Production | Updated Node table rows to check for null CPU/memory; rendered explicit `<span className="text-muted-foreground font-mono">N/A</span>` instead of fake percentage or progress bar. Genuine compute node display preserved. |
| `backend/tests/test_phase2_error_boundary_security.py` | Test | Added Section 9 with 5 comprehensive regression tests (Tests 9.1–9.5). |
| `audit/PHASE2_5_4_SYNTHETIC_TELEMETRY_REMEDIATION.md` | Audit | This document. |

---

## 4. OLD VS. NEW BEHAVIOR COMPARISON

### 4.1 Backend Data Contract
- **Old**:
  ```python
  class LiveDomainStatus(BaseModel):
      cpu_percent: float
      memory_percent: float
  ```
- **New**:
  ```python
  class LiveDomainStatus(BaseModel):
      cpu_percent: Optional[float] = None
      memory_percent: Optional[float] = None
  ```

### 4.2 External Ingested Links Dashboard Serialization
- **Old**:
  ```python
  "cpu_percent": 15,
  "memory_percent": 30,
  ```
  Result: Serialized `{"cpu_percent": 15.0, "memory_percent": 30.0}` to API clients for any GitHub/GitLab/external link.
- **New**:
  ```python
  "cpu_percent": None,
  "memory_percent": None,
  ```
  Result: Serialized `{"cpu_percent": null, "memory_percent": null}` to API clients. No fake numbers.

### 4.3 Runtime Compute Nodes Telemetry Preservation
- **Preserved Unchanged**:
  ```python
  for service_id, state in INGESTED_RUNTIME_STATE.items():
      metrics = state.get("metrics", {})
      status = state.get("status", "UNKNOWN").upper()
      cpu = int(metrics.get("cpu", 0) * 100) if metrics.get("cpu", 0) <= 1.0 else int(metrics.get("cpu", 0))
      memory = int(metrics.get("memory", 0) * 100) if metrics.get("memory", 0) <= 1.0 else int(metrics.get("memory", 0))
      ...
      monitored_list.append({
          "name": service_id.upper(),
          ...
          "cpu_percent": cpu,
          "memory_percent": memory,
          ...
      })
  ```
  Result: True host-agent / runtime container metrics remain numeric integer percentages (e.g., `45` and `65`).

### 4.4 Frontend Runtime Table Rendering (`frontend/src/app/runtime/page.tsx`)
- **Old**:
  ```tsx
  <td className="py-3">
    <div className="flex items-center gap-2">
      <div className="w-20 bg-secondary h-1.5 rounded-full overflow-hidden border border-border/40">
        <div className="bg-primary h-full rounded-full" style={{ width: `${item.cpu_percent}%` }} />
      </div>
      <span>{item.cpu_percent}%</span>
    </div>
  </td>
  <td className="py-3">{item.memory_percent}%</td>
  ```
- **New**:
  ```tsx
  <td className="py-3">
    {item.cpu_percent !== null && item.cpu_percent !== undefined ? (
      <div className="flex items-center gap-2">
        <div className="w-20 bg-secondary h-1.5 rounded-full overflow-hidden border border-border/40">
          <div className="bg-primary h-full rounded-full" style={{ width: `${item.cpu_percent}%` }} />
        </div>
        <span>{item.cpu_percent}%</span>
      </div>
    ) : (
      <span className="text-muted-foreground font-mono">N/A</span>
    )}
  </td>
  <td className="py-3">
    {item.memory_percent !== null && item.memory_percent !== undefined ? (
      `${item.memory_percent}%`
    ) : (
      <span className="text-muted-foreground font-mono">N/A</span>
    )}
  </td>
  ```

### 4.5 Frontend Resource Utilization Chart (`frontend/src/app/page.tsx`)
- **Old**:
  Included all monitored items regardless of whether telemetry existed, generating misleading zero-bars or synthetic 15/30 bars.
- **New**:
  Filtered `resourceData = monitoring.filter(item => item.cpu_percent !== null || item.memory_percent !== null)`. External links without telemetry are not plotted into the compute node resource chart; tooltips render `"N/A"` for missing values; empty state gracefully displays: `"No active compute node telemetry available (External links: N/A)"`.

---

## 5. CLARIFICATION ON REMAINING HEURISTICS

In accordance with Requirement 5 (*"Do not confuse heuristics with measurements"*):
1. **Hash-Derived Link Metrics**:
   - `_calculate_health_score(link)`
   - `response_time_ms: item.get("response_time_ms", 150)`
   - `uptime_percent: item.get("uptime_percent", 99.9)`
   - `errors_24h: item.get("errors_24h", 0)`
   These values are **heuristics / simulated baseline scores**, NOT measurements from host agents or live probes.
2. In this remediation, their existing behavior was preserved to avoid expanding the task scope into redesigning all heuristics, but they are explicitly classified here as heuristics, not genuine telemetry.
3. Conversely, host CPU and memory were previously presented as direct system measurements (`15%` and `30%`), which was objectively false. That fabrication has been removed.

---

## 6. SEARCH FOR REMAINING SYNTHETIC VALUES

A full scan across the Pravah codebase was conducted for:
- `cpu_percent": 15`
- `memory_percent": 30`
- `cpu_percent = 15`
- `memory_percent = 30`

**Result**:
- `backend/control_plane/backend/app/main.py:750-751`: REMOVED and replaced with `None`.
- Zero other instances exist anywhere in production paths.
- No other fallback constants (e.g., substituting `0` or `100` for external link resources) are present.

---

## 7. TARGETED REGRESSION TESTS PROOF

Added to `backend/tests/test_phase2_error_boundary_security.py` under Section 9:

### Test 9.1: `test_external_ingested_link_cpu_memory_is_none`
- **Objective**: Proves that external links in `_INGESTED_LINKS` produce `cpu_percent is None` and `memory_percent is None`.
- **Assertions**:
  - `ext_service["cpu_percent"] is None`
  - `ext_service["memory_percent"] is None`
  - `ext_service["cpu_percent"] != 15`
  - `ext_service["memory_percent"] != 30`
  - `ext_service["cpu_percent"] != 0`

### Test 9.2: `test_runtime_compute_node_metrics_remain_numeric`
- **Objective**: Proves that genuine compute nodes in `INGESTED_RUNTIME_STATE` retain real numeric telemetry.
- **Assertions**:
  - `s1["cpu_percent"] == 45` and `isinstance(s1["cpu_percent"], int)`
  - `s1["memory_percent"] == 65` and `isinstance(s1["memory_percent"], int)`
  - `s2["cpu_percent"] == 82` and `isinstance(s2["cpu_percent"], int)`
  - `s2["memory_percent"] == 91` and `isinstance(s2["memory_percent"], int)`

### Test 9.3: `test_live_dashboard_payload_pydantic_serialization_with_none_resources`
- **Objective**: Proves that `LiveDomainStatus` and `LiveDashboardResponse` validate and serialize nullable resource telemetry.
- **Assertions**:
  - Pydantic validation succeeds with `cpu_percent=None` and `memory_percent=None`.
  - JSON serialization yields `"cpu_percent": null` and `"memory_percent": null`.

### Test 9.4: `test_no_synthetic_15_30_values_for_external_links`
- **Objective**: Proves that across a diverse set of external URLs (GitHub, GitLab, custom domains), no 15/30 fallback constants are emitted.
- **Assertions**:
  - All services have `cpu_percent is None` and `memory_percent is None`.
  - None have `15` or `30`.

### Test 9.5: `test_mixed_external_and_runtime_dashboard_payload`
- **Objective**: Proves that a mixed dashboard contains both nullable external links and numeric runtime nodes without conflict.
- **Assertions**:
  - Runtime service has numeric `cpu_percent=50` and `memory_percent=70`.
  - External link service has `cpu_percent=None` and `memory_percent=None`.

### Targeted Test Execution Result:
```
pytest -q backend/tests/test_phase2_error_boundary_security.py
.........................................                                [100%]
41 passed, 37 warnings in 1.95s
```

---

## 8. FULL TEST SUITE & FRONTEND VALIDATION

### 8.1 Full Pytest Suite Result
Command: `pytest -q`
```
============================== 353 passed, 396 warnings in 22.48s ==============================
Exit Code: 0
```
Every test across the entire Pravah repository passed with zero errors or failures.

### 8.2 Frontend TypeScript Typecheck Result
Command: `npx tsc --noEmit` (in `frontend/`)
```
Exit Code: 0
Stdout: (empty - clean build)
Stderr: (empty)
```
All React components, hooks, and pages typecheck cleanly with the nullable `number | null` contract.

---

## 9. REPOSITORY INTEGRITY & VANA DIFF

### 9.1 VANA Diff
Command: `git diff -- VANA/`
```
Exit Code: 0
Output: (completely empty)
```
VANA was completely untouched.

### 9.2 Repository Hygiene
- No scratch files created.
- No debug helper files created.
- No unauthorized files modified.
- All modifications strictly confined to the authorized list.

---

## 10. FINAL CLASSIFICATION: A

**Classification Criteria Evaluation**:
- [x] Fabricated `cpu_percent = 15` and `memory_percent = 30` external-link telemetry completely removed from production paths.
- [x] External-link unavailable telemetry is explicitly represented as `None` / `null` / `"N/A"`.
- [x] Frontend no longer renders fake percentages or misleading resource bars for external links.
- [x] Genuine runtime compute-node metrics remain intact as numeric values.
- [x] Tests prove both paths (external link nullability and runtime node numeric preservation).
- [x] Full pytest passes (**353 passed**, 0 failed).
- [x] Frontend TypeScript typecheck passes with 0 errors.
- [x] `git diff -- VANA/` is completely empty.
- [x] No unauthorized files created.

**FINAL CLASSIFICATION: A**
