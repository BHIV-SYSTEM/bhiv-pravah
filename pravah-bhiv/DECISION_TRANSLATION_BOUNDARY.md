# DECISION TRANSLATION BOUNDARY

This document defines the architectural boundary between Group 2's scientific context and the Governance Engine's decision-making requirements.

## Why These Are Separate Layers
Scientific information and governed action decisions are fundamentally different domains. A scientific context artifact (e.g., environmental risk, confidence score) represents an observation about the world. A `DecisionContract` represents a specific, actionable intent (e.g., restart, scale_down). Directly coupling them creates a security vulnerability where an external science layer could theoretically mint execution authority. This boundary ensures separation of concerns.

## Current Missing Component
There is no existing transformation layer in the repository that translates a `contextual_result` from Group 2 into a valid `DecisionContract` required by the Governance layer. This represents a missing decision layer.

## Input Responsibility
- **Input**: `contextual_result` (produced by Group 2).
- **Responsibility**: Receive scientific context (e.g., environmental risk, confidence levels, findings).

## Output Responsibility
- **Output**: `DecisionContract` (consumed by Governance).
- **Responsibility**: Translate the scientific context into a **candidate decision**.

## Information Must Be Supplied by Group 2 Before Implementation
- Explicit confirmation on whether Group 2 provides only pure scientific context or if they include a recommended operational action.
- The exact schema of `contextual_result`.

## DecisionContract Fields Must Be Produced
The translation layer must synthesize and produce a valid `DecisionContract` containing:
- `decision_type` (e.g., "execution")
- `action` (e.g., "restart", "scale_down", "noop")
- `parameters` (dict)
- `version`

## Security Boundary
This Translation Layer acts strictly as a **decision synthesis boundary**. 

- **No Execution Authority**: The translation layer **CANNOT and MUST NOT** mint execution authority. It only produces a decision *candidate*.
- **Final Authority**: The `ActionGovernance` and `ExecutionRightsAdapter` components remain the absolute final execution authorization boundary. The Governance layer will evaluate the `DecisionContract` candidate against defined deterministic policies before granting actual execution rights.
