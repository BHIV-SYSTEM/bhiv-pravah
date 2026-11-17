# Temporal Applicability Ruling

## 1. Purpose
To determine whether the validated scientific context is temporally applicable to the actual observation, yielding a deterministic ALLOW, ADAPT, or GAP ruling.

## 2. Owner
Kaushal (Group 2 Temporal Applicability Ruling Owner)

## 3. Observation Identity
**Observation ID**: TC-Z03-F02-LIDAR-OBS001

## 4. Context Identity
**Context ID**: f47ac10b-58cc-4372-a567-0e02b2c3d479 (SUPERSEDED)
**New Context ID**: ctx-tc-001

## 5. Actual Temporal Evidence
- **Context Valid From**: 2020-01-01T00:00:00Z
- **Context Valid To**: 2028-12-31T23:59:59Z
- **Observation Timestamp**: 2026-08-13T09:14:22Z

## 6. Decision Rules
- **Missing temporal evidence**: -> GAP
- **Observation inside validity window**: -> ALLOW
- **Observation outside validity window with adaptation rule**: -> ADAPT
- **Observation outside validity window without adaptation rule**: -> GAP

## 7. ALLOW Definition
Action eligibility may proceed according to the frozen Group 2 -> Group 4 contract. (Evidence establishes observation is strictly within the context validity window).

## 8. ADAPT Definition
Explicit adaptation rule exists for the specific parameter. Abstention required until adapted.

## 9. GAP Definition
Temporal applicability cannot be established (missing evidence, stale evidence, or no adaptation path). Must NEVER become an Action Request.

## 10. Decision Table
| Case | Ruling | Eligibility | Abstention |
|---|---|---|---|
| Within Window | ALLOW | True | False |
| Outside (w/ Adapt) | ADAPT | False | True |
| Outside (no Adapt) | GAP | False | True |
| Missing Evidence | GAP | False | True |

## 11. Actual Ruling for TC-Z03-F02-LIDAR-OBS001
- **Ruling**: ALLOW
- **Reason**: Verified observation timestamp falls within the authoritative 2020–2028 context validity window.
- **Context ID**: ctx-tc-001

## 12. Test Results
- **Temporal tests**: PASS
- **Identity mismatch tests**: PASS

## 13. Determinism Evidence
100 consecutive runs of the deterministic evaluator with the identical input produced 100 exactly matching outputs. Result: PASS.

## 14. Identity Evidence
The observation and context IDs are rigorously preserved without manipulation. Result: PASS.

## 15. Provenance Evidence
- **Contract Version**: group2.temporal-applicability.v1
- **Authority**: Group 2 Temporal Applicability

## 16. Known Limitations
- None. (Previously, the observation timestamp was missing, forcing a GAP ruling. It has since been resolved with the canonical V2.2 payload).

## 17. Handoff Information
- **To Sakshi (Group 2 -> Group 4)**: The ruling payload `temporal_applicability_ruling.json` explicitly mandates `action_eligibility=True` and `abstention_required=False`. 
- **To Vijay**: The final machine-readable context retrieval should pick up the generated `temporal_applicability_ruling.json`.
