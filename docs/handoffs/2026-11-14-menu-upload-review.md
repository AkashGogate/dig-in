# 2026-11-14-menu-upload-review: in-app menu setup

- Owner role / coordination claim: Menu/Core shared-client integration, explicitly
  requested by the user. No other agents were spawned or teammate review assumed.
- Branch / base commit: `codex/menu-upload-review`, isolated local clone at
  `c1d25fc08e6cee5cdd74949211be38601f39f7c7` with the existing uncommitted Menu/Core
  implementation copied as the task baseline. Only this task's changed paths are
  copied back after content-hash concurrency checks. No staging/commit/push/deploy.
- Claimed paths / dependencies: frontend index.html/app.js/mvp.css; new
  menu-setup.js and tests/menu-setup.test.cjs; CI and affected workflow/status docs.
  Consumes existing menu prepare/activate contracts; no backend schema changes.
- Goal / acceptance criteria: a lead can upload/paste, automatically encode,
  inspect a canonical preview and explicitly activate a menu entirely in the app.
  Stale/edited previews cannot activate, uncertain activation uses exact retry,
  and old orders remain on their original menu.
- Implemented changes: secondary Menu setup screen with native file input and
  paste/format/name controls; automatic preparation on file selection, async
  encoding status, review of item/alias/modifier/price/kitchen data and warnings,
  review checkbox/explicit activation, permission/error/success/stale states.
  Existing dispatch owns activation/idempotent retries. Inputs/previews invalidate
  on source/session changes; source content is escaped and never stored locally.
  Shared request supports a longer preparation timeout. Open-draft menu note now
  rerenders when active menu changes; service workflows otherwise stay intact.
- Contract/schema compatibility and dependent reviewers: existing v2 endpoints and
  activate_menu command unchanged. Module receives request/dispatch/context from
  app.js and shares its exact-retry path. Voice/CV/Databricks contracts unchanged.
  Shared-client teammates should review the integration before team merge.
- Checks actually run, results, date: 2026-11-14. 113 backend tests passed using
  cached Python3.11.18 dependencies. App/module JavaScript syntax passed; 9 UI
  behavior cases passed in Node VM with native assertions (CI node --test configured
  but remote CI not run). Browser file chooser uploaded eight-dish JSON, automatic
  encoding/review/activation passed, old/new selectors preserved. CSV paste and
  Space→Tab→Enter activation passed; malformed JSON retained input with recovery.
  No menu-setup horizontal overflow at 320/768/1280 CSS px. Visible keyboard focus
  measured 3px. Final browser console had no error entries. Screenshot captured.
- Mocked/experimental/unverified behavior: browser used local lexical embeddings
  and fake analytics only. No paid calls/credentials. Tests emulate network errors,
  session races and uncertain retry; browser checks do not establish real semantic
  accuracy, screen-reader access, actual 200% zoom, cross-browser or phone quality.
- Remaining task / blocker / next owner: complete for structured JSON/CSV/TXT input.
  Arbitrary PDF/photo extraction, persistent menu storage/auth, and deliberate live
  provider enablement/quality checks remain separate work.
- Integration notes and potential conflicts: preserve prior uncommitted backend/
  menu work and unrelated files. Script order is config → menu-setup → app (defer).
  CI now syntax-checks the module and runs its dependency-free Node behavior tests.
  Keep the two primary service screens and the secondary menu setup surface.
