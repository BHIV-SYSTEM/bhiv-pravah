# Replay Corruption Report

Scope:
- Tampered replay payloads
- Ordering corruption
- Unsigned replay events

Outcome:
- All corruption cases are rejected by the existing replay and lineage controls.
- Rejection is deterministic and exercised through the real replay entry point.

Validation:
- `.venv\Scripts\python.exe -m pytest tests/adversarial_test_suite/test_tampered_replay.py tests/adversarial_test_suite/test_order_corruption.py tests/adversarial_test_suite/test_unsigned_events.py -q`