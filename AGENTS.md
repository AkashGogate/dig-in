# Dig In agent bootstrap

1. Inspect `git status`, current branch/worktree, and instructions in your claimed paths. Preserve others' uncommitted work. Never reset, force-push, or overwrite main to integrate work.
2. Read [docs/INDEX.md](docs/INDEX.md), [PROJECT_SPEC.md](PROJECT_SPEC.md), then [docs/STATUS.md](docs/STATUS.md). Read architecture/contracts and your work lane before editing. These Git-tracked files provide portable context; they are not automatic memory sync.
3. Claim a scoped task/paths with the integration-owner slot per [DEVELOPMENT](docs/DEVELOPMENT.md). Use a task branch and one clone/worktree per collaborator. Shared-contract changes need explicit dependent-lane review. Handoff in one file per task; STATUS is never a concurrency lock.

## Invariants

- Manual UI always works. Voice proposes a visible diff; only human **Confirm and send** submits the reviewed draft revision. No speech/model submission or payment authority.
- Signed-in session supplies actor identity. Demo sessions are simulated auth. Optional table suggestion only on Start order; selected table freezes until explicit correction.
- No dining-room video/guest tracking. Exactly two conceptual kitchen views: ingredient zones and plating bays. Observations are evidence, not accepted commands.
- Acknowledged ≠ preparing; staged/partially plated ≠ ready; pickup ≠ served. Aggregate all dish units. Human cook readiness by default; constrained auto-ready is experimental and disabled.
- Recipe expectations and accepted visual movements cannot both deduct stock. Preserve unresolved attribution and provenance. Never infer prep percentage from withdrawals.
- No overlapping bay assignments/reuse with food or unresolved pickup. Reject stale revisions/assignment versions. Claims and helper slots must be atomic and idempotent.
- Backend is shared authority. Surface outages/degraded adapters; never fabricate integration success. No production auth/durability, CV, POS, payment, or hardware claim without evidence.

## Map and checks

- `backend/app/coordination/`: executable contracts, deterministic fixtures, domain, adapters, API. `/api/v1/contracts` and FastAPI `/openapi.json` expose interfaces; do not independently redefine shapes in voice/vision/UI.
- `backend/app/`: retained kitchen-call parser, mismatch detector, capped audio sessions, SQLite log, legacy WebSocket server.
- `frontend/`: static role UI; `legacy.html` retains the original mic/scenario experiment. No Node framework/build migration.
- `backend/tests/`, `backend/eval/`, `audio-samples/`: invariants, transcript tests, synthetic-audio harness. Mock eval scores do not measure STT quality.
- `docs/`: product/architecture, collaboration lanes, status, decisions, runbooks, per-task handoffs.

Use README commands for setup/run; run `cd backend && uv run pytest -q` for the existing locked environment. Consult STATUS for commands actually verified in this scaffold. No paid key is required for coordination mocks. Do not publish, push, or enable billable integrations without explicit authorization. Update your task handoff and affected status/contract docs with evidence and limitations.
