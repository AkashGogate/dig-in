# Context map

Minimum path for a new contributor: root [AGENTS](../AGENTS.md) → [product](../PROJECT_SPEC.md) → [status](STATUS.md) → [development workflow](DEVELOPMENT.md). Inspect Git status, branch, scoped instructions, claimed paths, and shared-contract dependencies before editing.

| Need | Source of truth |
| --- | --- |
| Current behavior intended | [PROJECT_SPEC](../PROJECT_SPEC.md) |
| Implemented/mock/planned and checks | [STATUS](STATUS.md) |
| Boundaries, runtime and data flow | [ARCHITECTURE](ARCHITECTURE.md) |
| Executable schemas and protocol | [API](API.md), `backend/app/coordination/contracts.py`, `/openapi.json` |
| Cross-computer work and contract review | [DEVELOPMENT](DEVELOPMENT.md) |
| Role slots and path ownership | [WORKSTREAMS](WORKSTREAMS.md) |
| Why scope changed | [DECISIONS](DECISIONS.md) |
| Reproduce and evaluate | [DEMO_PLAN](DEMO_PLAN.md), [TESTING](TESTING.md) |
| Hand off one task | [handoff template](handoffs/TEMPLATE.md) |
| Earlier experiment/deployment reports | [archive](archive/2026-11-14-legacy-context.md), historical evidence only |

Avoid duplicating domain facts across documents. Change product intent here only through PROJECT_SPEC and DECISIONS; keep implementation status in STATUS and actual fields in executable contracts.
