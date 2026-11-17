# Known Limitations

This document lists architectural constraints and limitations identified during convergence testing.

---

## 1. Local Persistence Limitations
* **Problem:** Governance cooldowns and repetition logs are persisted in a local JSON file (`logs/control_plane/governance_state.json`). Thread-safety is achieved using a standard reentrant-safe thread lock, and process-safety is achieved by loading from disk on each check.
* **Impact:** In a multi-node/distributed deployment where multiple replicas of the FastAPI Control Plane are running, filesystem-based persistence is insufficient and will lead to split-brain governance.
* **Mitigation:** Upgrade the governance persistence layer to use a centralized distributed storage backend (such as Redis or a shared PostgreSQL database).

---

## 2. Docker Scaling Simulation
* **Problem:** When `EXECUTION_MODE` is set to `docker`, container scaling (`scale_up` and `scale_down`) is simulated as a log mock rather than physical container spawning.
* **Impact:** No actual containers are spun up during docker-mode scale actions. This is because native Docker does not support replica set counts natively outside of Docker Swarm or Kubernetes. (Rollouts and restarts remain fully functional in Docker).
* **Mitigation:** To test physical scaling, switch the executor to `kubernetes` mode (which rolls out pods and replicas).

---

## 3. Strict Trace Sequence Ordering
* **Problem:** The append-only `trace_logger.py` enforces a strict sequence validator (`detection -> payload_emitted -> action_received -> execution_result -> verification`).
* **Impact:** If multiple API calls or concurrent ingestion streams overlap in single-process uvicorn workers, the trace logger can throw a `ValueError` if stages interleave.
* **Mitigation:** The `/control-plane/runtime-ingest` endpoint runs `reset_trace()` to reset the sequence. For production, extend `trace_logger.py` to keep separate sequence validation contexts partitioned by `trace_id`.

---

## 4. Hardcoded Monitor Targets
* **Problem:** The Flask monitor app contains a static mapping dictionary of target services (`localhost:5001` and `localhost:5003`).
* **Impact:** Adding new services or modifying endpoints requires modifying the monitor codebase directly.
* **Mitigation:** Introduce a dynamic service discovery client or register service endpoints dynamically in the Control Plane database registry.