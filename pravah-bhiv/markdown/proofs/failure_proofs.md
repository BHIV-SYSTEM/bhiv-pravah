# Failure Proofs

Scope:
- Replay index dependency failure
- Concurrent replay reconstruction

Outcome:
- Readiness fails closed when the replay index dependency cannot be loaded as expected.
- Concurrent replay returns consistent lineage results across simultaneous reads.

Validation:
- `.venv\Scripts\python.exe -m pytest tests/adversarial_test_suite/test_dependency_failures.py tests/adversarial_test_suite/test_concurrent_replay.py -q`