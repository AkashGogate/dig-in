# 2026-11-14-menu-core-runtime: mutable menus and encoding

- Owner role / coordination claim: this task takes Menu/Core/backend integration,
  explicitly requested by the user. Names for the other lanes remain unassigned.
  No other agents were spawned; this file is not a lock or teammate signoff.
- Branch / base commit: `codex/menu-core-runtime`, isolated local clone from
  `main` at `c1d25fc08e6cee5cdd74949211be38601f39f7c7`. Task edits are uncommitted.
  Reviewed changes are copied to the user's checkout only after checking touched
  paths against that base; no staging, commits, remote push or deployment.
- Claimed paths / dependencies: menu.py, new menu_import.py/menu_embeddings.py,
  mvp contracts.py/domain.py/api.py; minimal compatible Voice suggestion callback,
  canonical events vocabulary, shared frontend menu binding; new runtime tests,
  eight-dish menu fixture, menu_tool.py, env/setup and affected integration docs.
  Consumes existing zone/command/outbox interfaces without replacing their authority.
- Goal / acceptance criteria: interchangeable structured menus normalize and
  automatically encode; explicit reviewed runtime activation with revision guards;
  preserve old drafts/tickets; suggestions never submit or erase uncertainty;
  Core integration remains usable during provider work/failure.
- Implemented changes: JSON/CSV/item-per-line importer, deterministic IDs and
  bounded validation, canonical descriptions/categories, content-revision indexes,
  credential-free hashing provider and opt-in OpenAI semantic adapter. New prepare,
  index and explicit search endpoints; lead/tap activation emits menu.activated.
  Orders pin revisions, labels and recipe interpretation; historical kitchen speech
  remains conservative. CLI outputs reviewable JSON and vectors. DIG IN fixture
  matches all eight artwork items with unknown kitchen data left unset.
- Contract/schema compatibility and dependent reviewers: additive v2 menu fields,
  state revision/history, order revision, line/dish modifier labels, activation
  command/event and submitted revision. /contracts exposes menu/import/search
  schemas. Voice callback is optional; operational voice uses only local vectors.
  Explicit search can call configured provider outside Core's lock. Voice,
  Databricks and shared-client consumers need team review before merge; no external
  lane review is claimed. CV commands/assignment versions are unchanged.
- Checks actually run, results, date: 2026-11-14, Python3.11.18/pre-existing cached
  dependencies. Full pytest 113passed (30 new cases); scoped Ruff lint/format
  34files passed; Node VM app.js syntax passed. Full-server real HTTP MVP smoke
  passed; eight-dish prepare/activate/retry/search + old draft preservation passed.
  CLI canonical JSON/vector generation passed. Browser showed new menu and old
  draft selector/modifiers plus preserved delivered ticket. The initial browser
  Confirm/send approval block was resolved after explicit user authorization:
  a fresh browser click passed with exactly one submitted event and two physical
  units after active-menu replacement. Original ticket fields stayed intact and
  acknowledgment/start/zone reservation remained separate. See the follow-up
  browser verification handoff.
- Mocked/experimental/unverified: local hashing is lexical, not AI semantics.
  Remote embeddings mocked only; no paid calls. Structured formats are implemented,
  arbitrary PDF/photo/prose extraction is not. No menu upload UI, durable versions,
  production auth, new stock-zone setup, real STT/CV/hardware/Databricks validation.
- Remaining task / blocker / next owner: Menu/Core reviews the contract additions
  with Voice/Databricks/client owners; team can add an upload/review surface and
  extractor adapter as needed. Semantic deployment requires deliberate provider
  configuration and real quality/latency/retention/access-control checks. Runtime
  persistence remains JSON-on-startup plus one-process memory.
- Integration notes and potential conflicts: domain/contracts/api, event vocabulary,
  voice callback, app.js, env and shared docs are shared paths. Retain existing
  unrelated edits. This task does not change default starter fixtures, v1/legacy
  state, live capture behavior or provider credentials. Exact command retries still
  require the original event ID, timestamp and content.
