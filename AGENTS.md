# Dig In agent bootstrap

1. Inspect `git status`, branch/worktree, scoped instructions and claimed paths. Preserve others’ uncommitted edits; never reset/force-push/overwrite main to integrate.
2. Use [agent task map](docs/AGENT_TASK_MAP.md) and [integration guide](docs/INTEGRATION_GUIDE.md) to locate change seams and dependent reviewers. Read [docs/INDEX](docs/INDEX.md) → [PROJECT_SPEC](PROJECT_SPEC.md) → [docs/STATUS](docs/STATUS.md), then your [workstream](docs/WORKSTREAMS.md) and contracts. These Git-tracked files provide portable context, not automatic memory sync.
3. The **Menu workstream also owns Core/backend and integration** (confirmed role decision); individual owner names remain unassigned. Agree task/path claims with that role. Separate clone/branch/worktree per task; shared contracts require dependent-lane review. Use a unique [handoff](docs/handoffs/TEMPLATE.md); STATUS is not a lock.

## Current MVP invariants

- Default app has **Server and Kitchen** screens against `/api/v2`. Manual entry/taps remain usable. Voice creates an editable menu-constrained draft; unknowns/ambiguity and spoken-table mismatch block send until explicit review. Only human **Confirm and send** on the current revision submits.
- Identity is the demo session/device, never a recognized speaker. Deliberate capture only; discard audio after transcription. Do not persist raw audio/transcripts/video in v2 state or analytics.
- On kitchen acknowledgment, reserve **K empty zones atomically for K physical dish units**. Quantity two needs two zones. No partial allocation/overbooking. Waiting orders retry FIFO as zones free; reject stale assignment versions.
- Ready-only plating convention: only finished plates enter assigned zones. Stable occupancy (default 1500ms, no hand) → dish ready; stable removal after occupancy → pickup/free. This recognizes occupancy, never food identity/modifiers/doneness. Blocked/offline/unknown is not empty; tap recovery remains available. Unexpected/returned plates need review.
- Submitted ≠ acknowledged ≠ started. Timers show elapsed/known typical minutes, never percent cooked. Partial ready count precedes one all-ready notification. Delivered is optional staff close-out.
- Ingredient detection is second priority: countable observations, review and accepted stock remain separate from recipe expectations; never double-deduct or infer progress from a hand.
- Canonical accepted/observed events keep stable ID, source time, identity and outcome. Duplicate retries do not repeat state changes or exports. Analytics drains outside requests; failures remain pending. No raw capture content or fabricated missing-stage durations.
- Bounded Server/Kitchen coordination and requested display/print/optional spoken summaries are authorized; see docs/SERVICE_COORDINATION.md. Dish lineups project canonical units, and handling an update never changes cooking/pickup facts. General positioning, independent task/helper/priority engine, courses, POS/payments and conversational spoken responses remain deferred. No dining-room camera, facial recognition or guest tracking. Legacy code is not the new authority.

## Map and checks

- `backend/app/mvp/`: v2 contracts/domain/fixtures/API, canonical menu and deterministic voice. `menu.py` owns menu shape; `contracts.py` owns operational shapes.
- `backend/app/mvp/cv_api.py`, `cv_bridge.py`, `cv-service/cvsvc/v2.py`: actual producer ingress and sampled, versioned evidence; read `cv-service/V2_INTEGRATION.md`. Standalone `kitchen-backend/` is isolated legacy, never a second app writer.
- `backend/app/analytics/events.py`: canonical event source. Outbox/adapters/analyzer plus `analytics/` SQL and simulated fixtures support Databricks work without cloud credentials.
- `frontend/index.html`, `app.js`, `mvp.css`: two-screen MVP; read `frontend/AGENTS.md`. `coordination-v1.html` and `/api/v1` preserve the broader scaffold; `legacy.html` preserves the older voice lab. These have separate state.
- `backend/tests/`, `backend/fixtures/`, `docs/`: meaningful regressions, portable examples, current decisions/workflow/status/handoffs. `/api/v2/contracts` and `/openapi.json` expose executable contracts.

Use [README](README.md) for setup/run, [TESTING](docs/TESTING.md) for checks, and STATUS for actual evidence. Default is a one-worker in-memory mock demo, not durable auth/cloud/CV/hardware. Update affected status/contracts and your handoff after changes. Do not push, publish or enable billable/live integrations without authorization.

Deployment composition lives in root Dockerfile/fly.toml and frontend/vercel.json/middleware.ts. Read docs/DEPLOYMENT.md for demo auth, shared HTTP proxy, direct ticketed WS, secrets and actual release gates. Branch watcher compares hashes only when unchanged; see docs/INTEGRATION_GUIDE.md.
