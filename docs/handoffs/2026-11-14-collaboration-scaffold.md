# collaboration-scaffold: portable team bootstrap and mock baseline

- Owner role: integration owner to assign before team integration. Parallel code/docs/UI/test edits were scoped by path for this task; no permanent teammate identities were invented.
- Branch/base: `codex/collaboration-scaffold`, base `051296d`.
- Scope: preserve the existing FastAPI/uv/static-frontend kitchen-call experiment; add shared coordination contracts/domain/mock seams, role screens, invariant checks, and portable collaboration context.
- Entry path: AGENTS → docs/INDEX → PROJECT_SPEC → docs/STATUS → architecture/API/workstream details.
- Contracts: schema v1 under `backend/app/coordination/`; frontend/speech/hardware consume centrally validated commands and generated schemas. Changes to consumers/semantics require explicit dependent-lane review. Existing legacy routes remain separate.
- Documentation changes: authoritative current product spec; archived original contradictory specs and deployment/migration reports; concise current decisions, workflow and lane ownership slots, runtime-state/Git-sync distinction, API/runbook/testing/status and per-task handoff template. No personal vault retrieval.
- Checks/evidence: 41 tests passed on Python 3.11.18; scoped Ruff lint/format and compile checks passed; real local HTTP smoke passed; Chrome manual order→diff→send→kitchen→partial→ready→pickup→served checked. Full results and untested limits are in `docs/STATUS.md`. No deployment, push, real payment, live provider or hardware integration is claimed.
- Limitations: simulated staff identity, transient single-worker backend, deterministic read-back/position/camera mocks. See STATUS for current scope gaps rather than inferring full product implementation from the product specification.
- Integration: review the local diff, assign shared-contract reviewers and integration owner, then transfer reviewed commits through the team's agreed Git workflow. Uncommitted worktree files are not automatically in the original checkout, remote, or teammates' clones. Never force-push or overwrite another contributor's changes.
