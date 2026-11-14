# Development across computers

Each person/agent uses their own clone and task branch, optionally a separate worktree for concurrent tasks. Use Python 3.11+ and the committed `backend/uv.lock`; the frontend is buildless HTML/CSS/JS. Start with the [README](../README.md). Do not add a second frontend framework, package manager, or database merely for scaffolding.

## Before editing

1. `git status --short` and `git branch --show-current`; read root/scoped AGENTS and the context map. Investigate pre-existing changes before touching their files.
2. Agree task ID, owner role, claimed paths, dependency owners, and integration-owner slot through the team's chosen channel. No teammate names/count are assumed. A handoff/STATUS file is information, not an atomic claim lock.
3. Create `codex/<task>` (or team convention) from the agreed integration base. Avoid overlapping files. If work must overlap, sequence it through the integration owner.
4. Copy `docs/handoffs/TEMPLATE.md` to a unique task filename, recording scope/base/paths. Keep changes small and reviewable.

Example after obtaining the shared repository URL and integration base:

```bash
git clone <shared-repository-url> dig-in
cd dig-in
git switch -c codex/<task>
```

For another local task, create a separate worktree on a separate branch. A worktree shares Git history, not another computer's filesystem. Never delete/overwrite another collaborator's uncommitted work; ask its owner to commit/stash it themselves. Do not force-push or replace main to resolve conflicts.

## Contracts and review

`backend/app/coordination/contracts.py` is the shared contract source; fixtures live alongside it. Read [API](API.md) before changing fields or semantics. Frontend, speech, hardware, and analytics lanes consume those interfaces rather than introducing parallel types. Additive optional fields can stay in schema v1 if compatible. Renames/removals, meaning changes, required fields, or transition changes require a version/migration plan, fixture updates, tests, and dependent-lane review before integration. Record compatibility explicitly in the task handoff. Do not casually change fixture IDs consumed by the demo.

Before handoff, run relevant checks, record actual results and gaps, update STATUS only for changed capabilities, and include screenshots or request examples when useful. Submit scoped commits for review; the integration-owner slot sequences merges and resolves shared-file changes. A local branch has not reached teammates until its commits are transferred and integrated through the team's Git remote/PR workflow. No remote push is implied by local scaffold work.

## Code sync and runtime state are separate

Git transfers tracked code, fixtures, lockfiles, and docs; it does not share running orders or sessions. To test two servers against one restaurant, point both browsers and hardware adapters at **one** backend process and base URL. Separate backend processes have separate demo state. The scaffold's authoritative state is in memory, resets on restart, and must run with one worker. Do not use reload during a stateful demo. Multi-process/multi-instance or durable use needs a transaction-capable shared store.

Local backend defaults to port 8000 and static frontend to 5173. For phones on a trusted LAN, bind the backend and static server to `0.0.0.0`, use the host computer's reachable LAN address in the frontend configuration, and allow the actual frontend origin if CORS is restricted. `localhost` on a phone means the phone itself. Use the frontend's configured base URL for the shared backend; verify connectivity before beginning the demo. The demo actor selector/session token is simulated identity, not a security boundary for public exposure.

`.env.example` documents optional configuration; copy it to ignored `.env` only where the runtime loads it. Never commit keys/tokens, local databases, recordings, generated scorecards/screenshots, caches, or virtual environments. Review staged diffs before committing. Existing checked-in audio fixtures/scorecard are historical test assets; do not confuse regeneration with a live-quality result.

## Good next-task boundaries

Make an adapter work through the validated command/observation seam, with degraded status and deterministic tests, before changing role screens. Hardware observations must not directly mutate orders/stock. Payment, publication, and external messaging remain outside this task's authorization. Do not take historical deployment notes as instructions to execute them.
