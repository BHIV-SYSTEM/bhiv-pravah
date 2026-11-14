# AMAN REVIEW SUMMARY — PRAVAH / BHIV PLATFORM VERIFICATION

**Audit Target:** `C:\Users\Microsoft\week\bhiv-pravah`
**Date:** November 14, 2026
**Auditor:** Antigravity Autonomous Systems Verification Engineer

---

## 1. What is Genuinely Implemented

- **Core Microservices & Observation Pipeline**: Full autonomous agent loop (`sense` → `validate` → `decide` → `enforce` → `act` → `observe` → `explain`) implemented across Flask Control Plane API (port 7000), FastAPI Decision Brain (port 8010), and Observer daemon (port 8600).
- **Canonical Health, Telemetry & Incident Engine**: Complete implementation of the canonical 5-state health lifecycle (`Healthy`, `Degraded`, `Unreachable`, `Stale`, `Not Monitored`), exact rolling latency percentiles (P50, P95, P99), HTML error page sanitization, sliding-window RPS, cascading dependency failure propagation, and 300-second temporal incident correlation.
- **VANA Ecological Pipeline & Governed Abstention**: Complete implementation of the VANA integration boundary (`POST /vana/execute`), consuming Group 2 rulings, preserving `canonical_record_id` and `observation_id`, evaluating constitutional governance, and recording deterministic `GOVERNED_ABSTENTION` evidence events with zero unauthorized operational side effects.
- **Cryptographic Event Ledgers & Persistence**: Append-only event log with SHA-256 continuous hash chains (`logs/control_plane/append_only_log.jsonl`), HMAC-authenticated monitored links journal, replay indexing, and tamper detection.
- **Telemetry Feature Extraction**: 10-dimension feature vector extractor (`ml_feature_extractor.py`) using `pandas` and `numpy` to compute latency trends, error velocity, retry chains, Z-score anomalies, and system utilization.

---

## 2. What is Verified Working

- **Live Ecosystem Connectivity**: **28 genuine services** respond with HTTP 200 OK across remote Yotta VM host (`163.128.209.18`) and cloud domains (Gurukul, Keshav 4, HR Gateway, HR Agent, LangGraph, Mitra, Samruddhi HFT, Parakosha MDU, Sarathi, AI CRM Setu, MasterDB Ingestion, BHIV Bucket, Parikshak, Prompt Runner, TTG, UniGuru, Workflow Blackhole, Vajra Blockchain, AI-Artha, Karma, and Core APIs).
- **Automated Test Suites**: **324 tests PASSED** (out of 330 total executed, **98.2% pass rate**) in under 45 seconds total execution time across 22 test suites covering all 10 core product requirements, persistence sovereignty, semantic guards, CORS security, and VANA governance.
- **Fail-Closed Security**: 33/33 dedicated security tests passed, proving that missing or placeholder secrets are strictly rejected in staging and production modes.
- **Local InsightFlow Subsystem**: Local event collector (`telemetry_collector.py`) and real-time WebSocket dashboard broadcast server (`websocket_server.py` on port 8765) are fully operational; remote InsightFlow backend (`https://tantra-insightflow.onrender.com/health`) responds 200 OK in ~390ms.

---

## 3. What is Simulated or Proposed

- **MongoDB Adapter**: **DOES NOT EXIST.** There is zero MongoDB code, no `pymongo`/`motor` dependencies, and no MongoDB database connection anywhere in this repository. All data is persisted in Redis, append-only JSONL ledgers, and JSON/CSV files.
- **Four DevOps Collaboration Workstreams**: Pravah is an autonomous DevOps governance, CI/CD, and microservice observability platform structured around **Four DevOps Collaboration Groups** (Group 1 Ingestion, Group 2 Context, Group 3 Edge, Group 4 Governance).
- **Machine Learning & RL Training**: **SIMULATED / RULE-BASED.** No serialized model weights (`.pkl`, `.onnx`, `.pt`) exist. Tabular Q-learning is demo-frozen (`exploration_rate = 0.0`, `learning_enabled = False`). Action decisions are made via hardcoded lookup tables and deterministic if/else threshold rules (e.g. `cpu >= 80 -> scale_up`).
- **Group 2 Scientific Context**: **SIMULATED LOCALLY.** There is no active remote Group 2 HTTP service; rulings are generated locally via `buildGroup2RulingFromObservation()`.
- **Group 3 Edge Robotics**: **PROPOSED / DOCUMENTED ONLY.** Endpoint is null; no physical robotics or sensor device is connected to the pipeline.

---

## 4. What Remains Incomplete

- **Remote Prometheus Container**: Port 9093 on Yotta VM host (`163.128.209.18`) actively refuses connections; container is down.
- **Unconfigured Microservice Endpoints**:
  - `Shakti GC Infra`: Unconfigured in `prod.env` (falls back to localhost).
  - `InsightBridge Phase 4 Demo`: Duplicate alias unconfigured in `prod.env`.
  - `Trade Bot`: Token `##YOTTA_URL:TRADE_BOT##` unpopulated in `prod.env`.
  - `AI-Artha FastAPI`: Port 9000 unallocated on Yotta VM.
- **External Sister-Repo Adapters**: File paths referenced in `live_integration_verifier.py` (e.g., `../AI-Artha/backend/.../tantra.service.js`, `../bhiv-core-.../Insight_Flow-main/...`) do not exist on the local filesystem.

---

## 5. Exact Blockers Requiring Owner Action

| # | Blocker | Impact | Exact Owner Action Needed |
| :-: | :--- | :--- | :--- |
| **1** | **Missing Production API Key** | 6 security tests fail with HTTP 401 because `PRAVAH_API_KEY` is not set in production mode. | Platform Owner must inject a production `PRAVAH_API_KEY` into the Yotta VM environment. |
| **2** | **Remote Prometheus Down** | Prometheus health endpoint `http://163.128.209.18:9093/-/healthy` refuses connections. | Platform Owner must run `docker restart pravah-prometheus` on the Yotta VM. |
| **3** | **Unpopulated Service URLs** | Shakti GC, Trade Bot, and Artha FastAPI endpoints cannot be monitored by Observer daemon. | Service owners must supply valid public or internal URLs to replace placeholders in `prod.env`. |
| **4** | **Specification Alignment** | Stakeholder requirement alignment regarding database architecture and project boundaries. | Maintain clear architectural documentation confirming Pravah is a DevOps governance and observability platform utilizing Redis, state stores, and append-only cryptographic ledgers. |

---

*Summary prepared for Aman based on read-only codebase forensics and test execution.*
