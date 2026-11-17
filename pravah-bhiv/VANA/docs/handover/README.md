# VANA Handover Documentation

Welcome to the VANA Control Center and Group 1 → 2 → 4 integration handover documentation. 

This directory contains empirical, verified evidence and architecture explanations of the pipeline's current state.

## Recommended Reading Order

1. **[VANA_COMPLETE_HANDOVER.md](VANA_COMPLETE_HANDOVER.md)**  
   *Start here.* The single executive document Mohit and Ansh can read to understand the entire architecture, data flow, and UI integration.

2. **[VANA_CURRENT_STATUS.md](VANA_CURRENT_STATUS.md)**  
   A quick-reference matrix of exactly what is LIVE VERIFIED, CODE VERIFIED, LOCAL VERIFIED, or NOT VERIFIED in the repository today.

3. **[VANA_ENDPOINT_CONTRACT.md](VANA_ENDPOINT_CONTRACT.md)**  
   The exact JSON contracts and HTTP verbs accepted and returned by the live deployed endpoints.

4. **[VANA_RUNTIME_EVIDENCE.md](VANA_RUNTIME_EVIDENCE.md)**  
   Hard evidence (curl outputs, replays, screenshots) proving the claims made in the status matrix.

5. **[VANA_GROUP3_GROUP1_HANDOFF.md](VANA_GROUP3_GROUP1_HANDOFF.md)**  
   Details on the source data (Open-Meteo) and how canonical identity is generated during ingestion.

6. **[VANA_GROUP4_HANDOFF.md](VANA_GROUP4_HANDOFF.md)**  
   Details on the boundary between Group 2 Context logic and Group 4 Governance execution.

7. **[VANA_CONTROL_CENTER_HANDOFF.md](VANA_CONTROL_CENTER_HANDOFF.md)**  
   Details on the VANA UI implementation (`http://localhost:4500/vana`), data rendering, and Next.js proxies.

8. **[VANA_VERIFICATION_RUNBOOK.md](VANA_VERIFICATION_RUNBOOK.md)**  
   Copy-pasteable PowerShell commands to manually run and verify the pipeline outside of the browser.

9. **[VANA_KNOWN_GAPS.md](VANA_KNOWN_GAPS.md)**  
   A list of unverified components, pending integrations, and remaining errors (e.g., Group 2 400 responses) that require attention.
