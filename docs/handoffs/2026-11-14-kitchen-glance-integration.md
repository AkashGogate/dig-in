# Kitchen glanceability increment — 2026-11-14

- Isolated clone: `/private/tmp/dig-in-kitchen-glance-20261114`, branch `codex/kitchen-glance-integration`, base `ac2ab55`.
- Actual incoming Git ancestry `163d9e84115331db2633607cbc8093837da38b41` fetched through root clone and merged `--no-commit --no-ff`. Working resolutions preserve the new Kitchen visual direction and all current authority. Only conflicts were `frontend/kitchen.html` and `frontend/UI_PLAN.md`; index remains pending for root’s real merge. No commit/push/deployment/paid call in this lane.

## Result

Incoming Kitchen CSS is retained verbatim. The canonical renderer now uses its `.ticket`, `.ticket-head`, `.dish`, `.d-status`, calm timer and bottom-count hierarchy. Tickets sort oldest valid submission first, with unknown sent times last; thresholds are 10m orange and 15m red, labeled “since sent.” Per-unit elapsed/typical time remains visible, missing start stages remain unknown, and no percentage/doneness inference exists.

Ready ratio uses ALL physical units of the ticket even with a station filter. The green actionable accent additionally requires every current zone assignment to belong to its unit and have no pending review; stage-ready counts remain honest when review blocks pickup. Bottom counts are current active physical units scoped to the displayed station and exclude picked-up/delivered history. Guest requests remain exact escaped visible text without inferred allergy classification; no unsupported source icons appear. Physical-zone assignment/review gates, acknowledge/start/manual-ready semantics, recipient-targeted update drafts, in-memory verified credential/session flow, indeterminate exact retry and explicit read-only summaries are preserved. Secondary update/summary/unit-detail disclosures reduce visual noise without removing actions. Document scrolling overrides prototype hidden overflow, keeping tall tickets reachable; mobile uses a vertical stack.

The latest original Kitchen source and UI plan are preserved byte-for-byte under `frontend/prototypes/ui-163d9e8/` as unloaded `.txt` references. Their fake IIFE/feed/Undo/mic/mock API behavior is not reintroduced.

## Frozen copy paths

```
frontend/kitchen.html
frontend/UI_PLAN.md
frontend/operator-pages.js
frontend/operator.css
frontend/tests/operator-pages.test.cjs
frontend/prototypes/ui-163d9e8/README.md
frontend/prototypes/ui-163d9e8/kitchen.html.txt
frontend/prototypes/ui-163d9e8/UI_PLAN.md.txt
docs/handoffs/2026-11-14-kitchen-glance-integration.md
```

Root owns the actual ancestry merge and final browser/layout/live-endpoint verification. No `app.js`, data transport, backend, config, server pages or shared root docs were changed. The test glob already includes the changed operator test file; no CI command changes needed.

## Checks

- Native Node22 syntax passed for `frontend/operator-pages.js`.
- Operator client/DOM suite: **23/23 passed**. Five new regressions verify oldest-first hierarchy/current all-ready accent, full-ticket ready ratio under station filter, and advancing submission-age labels with unknown times/focus preservation. Existing auth/retry/menu/guest-note/unit/summary/polling regressions pass unchanged.
- Full existing + incremental frontend suite: **53/53 passed** under native Node22. Astra independently cleared the focused source and operator regressions. These dependency-free tests are not a substitute for browser rendering/hardware/deployed verification.
- Incoming archived sources and retained active Kitchen CSS compared byte-for-byte against the fetched UI ref. `git diff --check` passed before freeze.
