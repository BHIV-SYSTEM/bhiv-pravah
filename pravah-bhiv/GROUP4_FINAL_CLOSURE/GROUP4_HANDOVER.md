# GROUP 4 HANDOVER

## A. What Group 4 guarantees

1. Action Request identity does not replace observation identity.
2. Observation ID is preserved.
3. Canonical Record ID is preserved.
4. Context ID is preserved.
5. Upstream provenance remains inspectable.
6. ALLOW creates eligibility, not execution.
7. Governance evaluates the Action Request boundary.
8. Duplicate delivery is idempotent.
9. Retrieval preserves original lineage.
10. Evidence remains CONTROLLED.

## B. Exact handover tuple

```text
observation_id:
TC-Z03-F02-LIDAR-OBS001

canonical_record_id:
group1-obs-20260813-9a3b

context_id:
ctx-tc-001

action_request_id:
ar-ac1ed033ff9e2941e05c28c8
```

## C. What Hemanth + Raj need to prove

They should consume the actual Action Request and demonstrate:

```text
Group 3
   ↓
Group 1
   ↓
Group 2
   ↓
Group 4
   ↓
Integrated Runtime
```

Specifically, they need to prove that the runtime does not substitute:

```text
observation_id
canonical_record_id
context_id
action_request_id
```

at any boundary.

## D. Current limitation

The Group 4 closure currently verifies lineage against a controlled
authoritative mapping fixture.

Live resolution against the actual Group 1 and Group 2 runtime or registry
remains an ecosystem integration responsibility.
