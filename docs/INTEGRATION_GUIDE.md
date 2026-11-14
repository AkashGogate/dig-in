# Teammate integration into Menu/Core

The scaffold supports effective incremental changes through explicit adapter and
contract boundaries. It is designed to be navigable and mutable by teammates and
agents; it does not make arbitrary changes automatically compatible. Integration
still requires review, tests and a shared runtime for live demo state.

## Four roles, one authority

Menu/Core owns canonical menu, commands/state, Core transaction, API ingress and
shared-client integration. Voice supplies reviewed draft/intent inputs; CV
supplies versioned zone evidence; Databricks consumes canonical events outside
requests. Adapters never mutate Restaurant state directly. Refer to WORKSTREAMS
for owned paths and AGENT_TASK_MAP for exact entry points.

## Contract-first handoff

Every lane supplies: base commit/branch, claimed paths, consumed/emitted schemas,
minimal fixture, normal/failure tests, mode/configuration, privacy/retention impact
and a unique handoff. Review additive fields with dependent consumers; breaking
semantics require a version/migration plan. /contracts and /openapi.json expose
executable shapes. Fixtures must use canonical menu IDs rather than copied dish
names. Fake and live adapters must share the same validation path.

Examples: speech replaces the Transcriber seam but still creates an editable
draft; camera supplies zone/version/time/stability/no-hand evidence but never
allocates zones; OCR replaces ocr_pages but still yields correctable records;
analytics replaces BatchAdapter.send but keeps event IDs/outcomes/source time and
background retries. Existing manual taps remain available in all these cases.

## Integrator checklist (local review, not an approval gate)

- Inspect both worktrees; preserve others' uncommitted changes. Transfer commits
  only through the agreed branch/PR workflow. Do not stage/commit/push on behalf of
  this user without authorization; do not overwrite main or force-push.
- Apply schema/import/fixture changes before consumer changes. Sequence shared
  domain.py/contracts.py/api.py/app.js edits and resolve conflicts deliberately.
- Run `uv run pytest -q` and scoped Ruff checks from backend (TESTING has commands).
  Run `node --test frontend/tests/*.test.cjs` from root and syntax checks.
- Start one fresh backend; perform HTTP smoke and the changed browser/device
  path. Test duplicate retry, invalid/stale input, unavailable adapter and manual
  fallback where relevant. Do not use paid APIs to prove credential-free logic.
- Record exactly what ran, what was mocked and what remains unverified in STATUS
  and the task handoff. Only then propose the next authorized Git transfer step.

Separate clones do not share in-memory orders. Phones, kitchen, speech and CV
must target one reachable backend with one worker. Backend restart loses demo
state/candidates/pending outbox. Auth, persistence and distributed execution remain
separate architectural work, not an adapter toggle. No automatic Git sync or
remote publication is provided by Markdown documentation.

## Preserving both user journeys

A teammate change must state its effect on Server, Kitchen and their connection.
Use SERVICE_COORDINATION as the journey contract. A projection must not invent a
second cooking lifecycle; notification/update handling must not silently advance
food. Summary/TTS/print consumers are read-only presentation over structured facts.
Test two server sessions and a kitchen session to catch recipient leakage; test
menu replacement while existing orders remain open. Preserve new snippets in
focused modules with a unique handoff; do not replace the shared scaffold wholesale.
