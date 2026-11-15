# Context map

Minimal fresh-agent path: [AGENTS](../AGENTS.md) → [PROJECT_SPEC](../PROJECT_SPEC.md) → [STATUS](STATUS.md) → [WORKSTREAMS](WORKSTREAMS.md) → [DEVELOPMENT](DEVELOPMENT.md). First inspect Git status/branch, scoped instructions, claimed paths and contract dependencies. Menu owns Core/backend/integration as a role; people remain to be named.

| Need | Source |
| --- | --- |
| Server and Kitchen journeys, updates and summaries | [SERVICE_COORDINATION](SERVICE_COORDINATION.md) |
| Requested integration acceptance and external gaps | [INTEGRATION_ACCEPTANCE](INTEGRATION_ACCEPTANCE.md) |
| Submission scope/security/hygiene audit | [SUBMISSION_AUDIT](SUBMISSION_AUDIT.md) |
| Agent entry points by task | [AGENT_TASK_MAP](AGENT_TASK_MAP.md) |
| Teammate integration workflow | [INTEGRATION_GUIDE](INTEGRATION_GUIDE.md) |
| Incoming UI source/contracts | [Frontend integration](../frontend/INTEGRATION.md), [UI handoff](handoffs/2026-11-14-ui-application-integration.md) |
| Fly/Vercel auth, routing, image and release checks | [DEPLOYMENT](DEPLOYMENT.md), [signed-in release handoff](DEPLOYMENT_HANDOFF.md) |
| Read-only checks after main pushes and manual release verification | [LIVE_MONITORING](LIVE_MONITORING.md) |
| Actual CV producer into shared Core | [CV integration](../cv-service/V2_INTEGRATION.md) |
| PDF/photo extraction and correction | [MENU_EXTRACTION](MENU_EXTRACTION.md) |
| Current MVP intent | [PROJECT_SPEC](../PROJECT_SPEC.md) |
| Supplied brief normalized for teammates | [MVP_TEAM_BRIEF](MVP_TEAM_BRIEF.md) |
| Implemented/simulated/adapter-only/future and actual checks | [STATUS](STATUS.md) |
| Runtime and data flow | [ARCHITECTURE](ARCHITECTURE.md) |
| Operational/menu/event contract + v1 migration | [API](API.md), `backend/app/mvp/`, `backend/app/analytics/events.py` |
| In-app menu upload/review, vectors, activation and snapshots | [MENU_PIPELINE](MENU_PIPELINE.md) |
| Four roles, core/screen responsibility, next handoffs | [WORKSTREAMS](WORKSTREAMS.md) |
| Git code transfer versus runtime shared state | [DEVELOPMENT](DEVELOPMENT.md) |
| Scope changes/provisional decisions | [DECISIONS](DECISIONS.md) |
| Reproduce/check/demo | [DEMO_PLAN](DEMO_PLAN.md), [TESTING](TESTING.md) |
| Databricks metrics, simulated data and SQL | [Analytics README](../analytics/README.md) |
| Unique task handoff | [Current integration checkpoint](handoffs/2026-11-14-service-flow-integration.md), [template](handoffs/TEMPLATE.md) |
| Earlier scope/evidence | [v1 scaffold](archive/2026-11-14-v1-scaffold.md), [original experiment](archive/2026-11-14-legacy-context.md) |

Keep intent in PROJECT_SPEC, execution evidence in STATUS and field shapes in code. Docs synchronize only when commits are transferred through Git; they are not tool-agnostic memory synchronization.
