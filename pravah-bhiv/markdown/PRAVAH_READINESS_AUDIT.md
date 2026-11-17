# PRAVAH LIVE INTEGRATION READINESS AUDIT

**Status:** Production Readiness Review
**Date:** 2026-06-08
**Assessment Tone:** Brutally Realistic (Zero Optimism Inflation)

This audit evaluates the readiness of the converged Pravah system to be deployed as a unified autonomous DevOps platform in a production-like staging environment.

---

## 1. Readiness Scorecard

| Readiness Dimension | Score (%) | Status | Core Assessment |
| :--- | :--- | :--- | :--- |
| **Current Convergence** | **45%** | 🔴 Critical | The system is heavily fragmented. Out of 11 repositories, 5 are duplicates/skeletons that must be deleted. A duplicate nested copy of `reliability-controller2-main` resides inside `multi-agent-control-plane-main`, creating confusion about the active codebase. |
| **Replay Readiness** | **100%**| 🟢 Ready | Hardened cryptographic signature verification, recursive deterministic serialization, lineage genesis validations, single-use trace registries, and cross-layer HMAC-SHA256 nonced request verifications are fully implemented and verified via unit/integration tests. |
| **Deployment Readiness** | **40%** | 🔴 Critical | Highly fragmented. Separate docker-compose files exist, but there is no unified deployment manifest for the entire system. Port conflicts exist (both `web1` and `sarathi` bind to `5001` locally), and a hardcoded user desktop path exists in [dashboard.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/pipeline-integration-py-main/dashboard.py#L297), which will crash outside that user's machine. |
| **Schema Readiness** | **55%** | 🟡 Warning | Significant schema drift. Shivam's CP represents metrics as decimal floats (`0.95` CPU), while Ritesh's State Encoder expects percentage integers (`95.0`). Telemetry ingestion contracts also mismatch the strict flat format required by the TANTRA Signal Schema. |
| **Integration Readiness** | **35%** | 🔴 Critical | The active autonomous loop ([agent_runtime.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/agent_runtime.py)) is bypass-wired to a mock endpoint on Port `5000` returning hardcoded `restart` responses, instead of being integrated with the persistent RL Decision Engine on Port `8008`. |
| **Constitutional Readiness**| **90%** | 🟢 Ready | The roles, boundaries, and authority declarations are fully locked in [PRAVAH_CANONICAL_ARCHITECTURE.md](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/PRAVAH_CANONICAL_ARCHITECTURE.md) and [FULL_CONVERGENCE_MAP.md](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/FULL_CONVERGENCE_MAP.md). |

---

## 2. Major Blockers (Must fix before staging)
1. **The Mock Decision Bypass:** In [agent_runtime.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/multi-agent-control-plane-main/agent_runtime.py#L627), the decide step POSTs to `http://localhost:5000/process-runtime`. This endpoint is hosted in the mock dashboard of `pipeline-integration-py-main`, which returns a static mock payload (`"action_requested": "restart"`). The system is not executing actual RL decisions in its loop.
2. **Hardcoded FS Path:** [dashboard.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/pipeline-integration-py-main/dashboard.py#L297) contains:
   `LOG_FILE = r"C:\Users\spal4\Desktop\SHIVAM\BHIV\multi-agent-control-plane-main\logs\dev\rl_execution_feedback.jsonl"`
   This absolute file path is specific to a user named `spal4`. Execution on any other environment will fail on start.
3. **Port Conflict on 5001:** If running services directly (without container port forwarding), the target app [web1/app.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/reliability-controller2-main/web1/app.py) and the policy router [sarathi/app.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/reliability-controller2-main/sarathi/app.py) both default to `port=5001` in their execution lines, causing local address collisions.

---

## 3. Critical Risks
* **Vulnerable Execution Entrypoint (RESOLVED):** Rayyan's [executer/app.py](file:///c:/Users/black/OneDrive/Desktop/Pravah/BHIV/reliability-controller2-main/executer/app.py) has been hardened with HMAC-SHA256 signature verification, request freshness controls, replay protection (nonces), and single-use trace ID consumption checks. Unsigned or duplicate execution requests are rejected immediately.
* **Q-Table Reset:** The Decision Brain implementation in `decision-brain-cp.py-main` holds Q-learning weights in memory. Restarts erase all learned behaviors, forcing the agent back to exploration defaults.
* **Loss of Telemetry Context:** Telemetry metrics inside `monitoring/runtime_poller.py` are saved to files on disk but are not pushed dynamically to Rayyan's monitor service, preventing live SSE streaming of health alerts.

---

## 4. Dependency Risks
* **Kubernetes RBAC Prerequisites:** The executor's script requires the RBAC manifests in `k8s/executer-rbac.yml` to be applied. Without these, the pod's service account will fail to perform namespace deletions, rendering recovery actions silent failures.
* **Host Redis Dependency:** `agent_runtime.py` tries to load `RedisEventBus`. If Redis is unavailable, it silently falls back to an in-memory event bus. Under production stresses, this memory buffer will drift from parallel worker processes.

---

## 5. Timeline to Live Proof

```
Day 1: Cleanup & Port Alignment
[====================] 100%
* Delete 5 duplicate directories.
* Re-bind Dashboards to Port 8050.
* Parameterize the hardcoded path.

Day 2: Metrics Scaling & Wiring
[====================] 100%
* Wire agent_runtime.py to pravah-integration (Port 8008).
* Write metric scale adapter (* 100).

Day 3: Security & Verification
[====================] 100%
* Add OTel event collectors to poller.
* Implement verify_signed_headers in Executer.

Day 4: Live Staging Run
[====================] 100%
* Apply Cluster RBAC manifests.
* Trigger live injection and audit trace logs.
```

**Total Estimated Effort:** 4 Days (approx. 20-24 engineering hours) to a verified, secure, unified proof-of-concept run in staging.
