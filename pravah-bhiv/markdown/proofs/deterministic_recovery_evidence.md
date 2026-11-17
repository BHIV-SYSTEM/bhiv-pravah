# Deterministic Recovery Evidence

Scope:
- Restart recovery validation
- Replay index rebuild behavior
- State hash stability across repeated recovery checks

Outcome:
- Recovery remains deterministic across repeated validation passes.
- The rebuilt replay index preserves the expected state hash and readiness outcome.

Validation:
- `.venv\Scripts\python.exe -m pytest tests/adversarial_test_suite/test_deterministic_recovery.py -q`