# Development across computers

Each collaborator uses a separate clone/task branch, optionally separate local worktrees. Use the committed uv lock and Python 3.11+; static frontend needs no Node build. Read [AGENTS](../AGENTS.md), [STATUS](STATUS.md) and [WORKSTREAMS](WORKSTREAMS.md). **Menu owns Core/backend and integration** as a role; no personal names are assigned.

## Before editing and handoff

1. Inspect `git status --short`, branch/worktree and scoped instructions. Preserve pre-existing edits.
2. Agree task ID, role owner, exact claimed paths and schema dependencies with Menu/Core integration. A STATUS/handoff file is information, not an atomic lock.
3. Create a separate `codex/<task>` branch from the agreed checkpoint. Avoid shared-file overlap; sequence schemas/entry points through Menu/Core. Copy [handoff template](handoffs/TEMPLATE.md) to a unique filename.
4. Consume v2 menu/operational/canonical event contracts rather than inventing parallel shapes. Compatible additions may remain v2; breaking field/meaning/state changes require explicit version/migration plan, fixtures/tests/consumer review.
5. Run relevant checks, record actual gaps/evidence and changed status, then submit small scoped commits for integration. Do not force-push/main overwrite or ask an agent to discard someone else’s uncommitted work.

## This checkpoint and remote transfer

Configured remote is [AkashGogate/dig-in](https://github.com/AkashGogate/dig-in.git). Local `main` tracks `origin/main`; `codex/collaboration-scaffold` has no upstream until explicitly pushed. A read-only `git ls-remote --heads origin main codex/collaboration-scaffold` check found origin/main at051296de and no remote scaffold branch; this was not a fetch or push. The scaffold is prepared locally, **not pushed** by this task.

After review and explicit authorization, the integrator can transfer the checkpoint:

```bash
git switch codex/collaboration-scaffold
git push -u origin codex/collaboration-scaffold
```

Only **after that push**, teammates can create their own task branches:

```bash
git clone https://github.com/AkashGogate/dig-in.git
cd dig-in
git fetch origin
git switch -c codex/<lane-task> origin/codex/collaboration-scaffold
```

Existing clones begin with a clean/reviewed status, then fetch and branch from the checkpoint. Do not make everyone commit to the same shared branch. The Menu/Core integrator reviews/merges lane work through the agreed PR workflow. A local worktree shares Git objects on one computer, not another machine’s files.

## Code sync and runtime state differ

Git transfers tracked code/docs/fixtures/lockfiles, not live orders or sessions. To coordinate phones/kitchen/hardware, point all clients at **one reachable backend process/base URL**. Separate backends have isolated in-memory states; multiple workers/reload/restart break the demo continuity. Durable/multi-instance operation needs a transaction-capable shared store, auth and durable outbox.

Default ports: API8000, static5173. For trusted LAN testing, bind both to `0.0.0.0`, use the host’s reachable LAN address in `frontend/config.js` and any adapter configuration, and verify frontend origin/CORS/connectivity before service. A phone’s localhost is the phone. Demo actor/device sessions are not production security.

`.env.example` documents active mode variables. Copy to ignored `.env` only where deliberately loaded (`uvicorn --env-file ../.env` from backend, or export variables). Never commit keys, raw recordings, local DBs, generated exports/screenshots/caches/environments. Checked-in synthetic audio and ten-order JSONL are labeled fixtures, not real restaurant observations. No live credentials, remote push, deployment or external messages are part of this local task.
