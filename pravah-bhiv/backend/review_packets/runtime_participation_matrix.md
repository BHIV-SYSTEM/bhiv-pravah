# Runtime Participation Matrix

**Date**: 2026-07-25
**Scope**: Ecosystem-wide execution tracking and participation

---

## 1. Participation Matrix

The following matrix documents Pravah's integration with key BHIV products. "Y" indicates confirmed integration/participation.

| BHIV Product | Registry Entry | Observer Probe | Telemetry Push | Evidence Bundle | Replay Index | Authority Level |
|---|---|---|---|---|---|---|
| `gurukul-backend` | Y | Y | Y | - | Y | passive_observer |
| `infiverse-hr-platform`| Y | Y | Y | - | Y | passive_observer |
| `parikshak-system` | Y | Y | - | - | Y | passive_observer |
| `trade-bot` | Y | Y | - | - | Y | passive_observer |
| `bhiv-sarathi` | Y | Y | Y | Y | Y | passive_observer |
| `ttg` | Y | Y | - | - | Y | passive_observer |
| `bhiv-karma` | Y | Y | - | - | Y | passive_observer |
| `bhiv-keshav-4` | Y | Y | - | - | Y | passive_observer |
| `workflow-blackhole` | Y | Y | - | - | Y | passive_observer |
| `uniguru_ai` | Y | Y | - | - | Y | passive_observer |

## 2. Definitions

- **Registry Entry**: The product is formally registered in `backend/control_plane/apps/registry/`.
- **Observer Probe**: The product's health endpoint is continuously monitored by the Pravah Observer.
- **Telemetry Push**: The product actively pushes runtime traces (via `PravahAdapter` or similar) to the Pravah Decision Brain.
- **Evidence Bundle**: Pravah has produced or stored a cryptographic evidence bundle detailing execution compliance for this product.
- **Replay Index**: The product's events exist and are tracked within the Pravah Replay Index and Append-Only Log.
- **Authority Level**: The governance authority granted to Pravah over the product (always strictly bounded to `passive_observer`).
