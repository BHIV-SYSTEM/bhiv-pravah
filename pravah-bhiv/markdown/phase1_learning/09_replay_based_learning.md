# 09. Replay-Based Learning Systems

In advanced machine learning ecosystems, models often need to be fine-tuned or retrained based on the actual outcomes of their past decisions. Replay-based learning involves saving the exact context of an event and the decision made, so it can be re-evaluated later.

## The Concept of a Replay Ledger
Instead of just logging a string of text (e.g., `throttle applied to service X`), the system must record the exact *input state* and the *output action*. This is stored in an immutable ledger (e.g., a `.jsonl` file).

### Why Replay is Necessary
1. **Model Drift:** Over time, the definition of "normal" traffic changes. A model trained on last year's data will trigger false positives today.
2. **Offline Reinforcement Learning:** By replaying a month of historical telemetry through a new experimental policy in a sandbox, engineers can prove the new policy is safer without risking live production downtime (Simulation/Shadow mode).

## PRAVAH & Parikshak's Implementation
PRAVAH integrates with systems like Parikshak to achieve this:
1. **Intake & Review Payload:** The exact state of the system is recorded.
2. **Cryptographic Hashes:** The event is hashed (`event_hash`) and linked to the previous event (`parent_hash`) to ensure the sequence of the replay ledger cannot be tampered with.
3. **Trace IDs:** By tagging the replay entry with the original `trace_id`, the system can join the offline learning data with the live production telemetry, providing a complete feedback loop.
