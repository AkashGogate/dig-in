# Status — MVP v2 checkpoint, 2026-11-14

[PROJECT_SPEC](../PROJECT_SPEC.md) owns intended behavior; this file owns execution evidence. [Normalized brief](MVP_TEAM_BRIEF.md) is portable team context. The Menu workstream **also owns Core/backend and integration**; personal names remain unassigned. STATUS is not a concurrency lock.

## Current application integration — 2026-11-14

The newest source is `codex/application-integration`, combining menu/service
9d3face, Voice9af39dc and CV3b0d0a1 with real merge ancestry. Older sections below
are historical local checkpoints, not the current deployment/access claim.

- **207 canonical backend tests, 47 CV tests and 44 standalone kitchen tests
  passed** in separate locked Python3.11 environments. **29 Node22 cases passed**,
  including actual Vercel middleware entrypoint, host configuration and PCM helpers.
  Ruff lint/format passed across54 scoped Python files. The inherited18-clip MOCK
  evaluator passed18/18 in the Voice lane; it supplies ground truth, not live STT.
- Full ASGI composition covers auth, runtime menu encoding/activation, old pinned
  drafts, voice review, actual CV event schema/bridge, targeted role updates,
  read-only summaries and pickup. Legacy binary paid audio is disabled. One
  Starlette/httpx deprecation warning remains in the Python app/legacy suites.
- Actual incoming CV modules are retained, with a strict opt-in canonical worker,
  capture-time assignment/version binding, continuous monotonic stability,
  confidence/real hand/calibration gates, heartbeat loss, recovery quarantine and
  individual frozen retries. Synthetic pixel/replay/mock-producer tests passed;
  no private frames, live camera, model download or physical rig were tested.
  Two real incoming calibration PNGs are removed from the integration tip and
  ignored locally; original branch history is preserved.
- Full-server local HTTP MVP smoke passed. In-app browser passed table-first
  simulated voice→editable quantity2 draft→human Confirm and send→Kitchen heard
  acknowledgment→two zones→one deliberate start→stable simulated first plate→
  requested Kitchen summary showing1of2 ready. No premature all-ready notification.
  This is a desktop local browser check, not a physical mic/phone/noisy-room test.
- Full HTTP demo Basic gate fails closed for partial/Fly config; Vercel static
  gate/proxy and direct session-ticketed voice endpoint are implemented. Public
  health is minimal; Docker/Fly configuration moved to root to package the exact
  CV schema owner. One machine/worker and memory-only limits remain mandatory.
  CI now includes all three suites, middleware tests and root container build/import.
- Live read-only check of the supplied domains found backend `/api/v2/state`200
  without login, backend `/healthz`404, frontend `/`200 without login and frontend
  `/api/v2/state`404. Those deployments still need the reviewed source/configuration
  and matching secret values. No actual hosted authentication/proxy/WS/upload
  success, container build or paid provider call is claimed by this local result.
- Local hourly branch heartbeat created: `watch-dig-in-integration-branches`. It
  compares remote hashes and stops when unchanged; changed refs are reviewed in
  isolation, preserving active work/main. No automated deployment or paid calls.
  The local app/machine must be available for scheduled runs; this is not a cloud
  availability monitor or a guarantee of zero integration conflicts.

See [DEPLOYMENT](DEPLOYMENT.md), [CV integration](../cv-service/V2_INTEGRATION.md)
and the [integration handoff](handoffs/2026-11-14-application-integration.md).
Teammate changes can be integrated effectively at these documented seams; arbitrary
snippets still need contract review and tests. Secrets belong in ignored `.env`
or platform stores, never chat/Markdown. Source checks and hosted readiness differ.

## Historical scaffold checkpoints

| Capability | Status / practical limit |
| --- | --- |
| FastAPI/Python/uv/static stack | Implemented, retained; no new platform/framework |
| Two primary Server/Kitchen screens, `/api/v2` | Implemented local demo; shared backend state, exact retry IDs; not native/offline transactions |
| Menu inputs/index/activation/matcher | Structured JSON/CSV/item-per-line import + reviewed runtime activation; local lexical vectors and opt-in semantic adapter; historical draft/ticket snapshots. See follow-up evidence below |
| Voice draft and kitchen grammar | Simulated transcript input with real parser/flags; no live microphone/STT/noisy-hall validation |
| Current-revision human send | Implemented; unknown/table mismatch explicitly resolved, voice cannot submit; correction counts defined in product/API |
| One-zone-per-physical-unit on ack | Implemented atomic all-K/FIFO retry/capacity/version rules; six simulated zones A–F |
| Ready-only occupancy/removal | Implemented event rules using simulated producer evidence (1500ms/no hand); no image detector or verified UNO Q feed |
| Camera blocked/offline/unexpected/tap recovery | Implemented demo status, unknown occupancy, review, tap-ready/pickup; no feed-health hardware proof |
| Per-dish start/timer, partial/all-ready/pickup/delivered | Implemented timestamps/progress and once-only all-ready notification; missing starts remain unknown; delivered optional |
| Ingredient tracking | Second-priority countable observation/review/movement scaffold, not real ingredient CV; expected recipe does not deduct |
| Canonical events/outbox/export | Implemented local contract, identity/time/outcome validation, background fake/JSONL retry/health; memory pending rows lost on restart |
| Databricks evaluation assets | 106 labeled SIMULATED events / ten orders /20 units, local analyzer and SQL/dashboard templates; no live dashboard/workspace tested |
| PDF/photo menu extraction; live STT/CV/Databricks | Local OCR/correction is implemented; live speech/CV/cloud adapters remain separate; no paid credentials needed |
| Legacy preservation | Frozen `/api/v1` broad coordination in coordination-v1.html and original legacy.html voice lab; isolated state/contracts, not MVP defaults |
| Deferred | Positioning, independent task/helper/priority engine, courses, general conversational spoken responses, POS/payments; bounded service coordination is described below |
| Production/deployment | No auth/durable state/multi-worker/outbox guarantee; no push/publication or cloud/hardware claim |

## Verified checkpoint evidence

Reported by the implementing lanes/root on macOS arm64/Python3.11.18, locked default environment:

- **83 tests passed** across retained regressions, menu/voice, analytics and new MVP core checks. Core tests cover manual/voice approval, table/unknown flags, atomic zone capacity/release, stable/blocked/tap fallback, idempotency, notification and voice ambiguity for same-table orders/quantity>1 units. One dependency deprecation warning remains from Starlette’s httpx TestClient transport.
- Scoped Ruff lint/format passed for the scoped Python paths. Frontend scripts parsed in Node VM; no frontend build exists. Exact final commands are in [TESTING](TESTING.md); root re-runs after integration as needed.
- Real HTTP `python -m scripts.mvp_smoke --base-url http://127.0.0.1:8001` **passed** against a fresh full server. Old `scripts.smoke_demo` remains explicitly v1.
- Chrome v2 flow **passed**: selected table1, captured spoken table2 with two dishes/modifier, saw flags/blocked Confirm, explicitly chose spoken table, sent, acknowledged and reserved two distinct zones. Stable first plate showed1of2; blocked camera plus second tap-ready emitted one all-ready notification; tap-pickup both followed by optional Delivered. Missing start time stayed unknown.
- No new full responsive/accessibility, screen-reader, cross-browser, physical phone, real noisy-room STT/CV, hardware throughput, container build or live Databricks workspace/dashboard checks were performed. Earlier v1 browser/eval results are [historical](archive/2026-11-14-v1-scaffold.md), not v2 coverage.
- Analytics fixtures/tests label data SIMULATED and exercise pending failure/retry/deduplication and missing-stage/denominator behavior. See [analytics README](../analytics/README.md) for sample counts and untested SQL/live limits.

The original saved checkout remains separate from the execution worktree. A read-only remote heads check found origin/main051296de and no remote scaffold branch; no fetch/push or automatic multi-computer synchronization is claimed. The local checkpoint is ready for review/authorized Git transfer, not already pushed.

## Remaining human decisions and next work

Name the four workstream people (Menu’s person also carries Core/integration), accept/refine proposed screen ownership, choose actual speech/camera/UNO Q rig and Databricks workspace. Kitchen microphone details/60second escalation/Free Edition availability remain provisional. Next adapters must preserve v2 contracts, privacy, failure recovery and manual paths; validate official live APIs/hardware before claiming completion. A durable transactional state/outbox and real auth are separate production work.

## Menu/Core follow-up — mutable menu pipeline, 2026-11-14

Structured JSON/CSV/item-per-line menus now prepare canonical records plus vectors
without dish-specific parser changes. Lead review + expected active revision
activates menu/index through the existing Core command transaction and canonical
outbox. Existing drafts/tickets and recipe expectations retain historical menu
revisions; the shared client keeps their original selectors/modifier labels.
An eight-dish DIG IN fixture now matches the existing artwork/prompt. See
[MENU_PIPELINE](MENU_PIPELINE.md) and the
[task handoff](handoffs/2026-11-14-menu-core-runtime.md).

- **113 tests passed** (83 prior + 30 menu-runtime cases). Coverage adds structured
  imports, invalid input, automatic encoding, stale/review/role guards, retry-safe
  activation/export, historical drafts/kitchen speech/recipe expectations,
  provider/vector failure, outbox rollback and operations during slow encoding.
- Scoped Ruff lint and format passed across 34 Python files. Changed `app.js`
  parsed in Node VM. Python3.11.18 used the pre-existing local dependency cache;
  no new runtime dependency or lockfile change was needed.
- Full-server real HTTP MVP smoke passed. Additional real HTTP prepare→encode→
  activate→exact retry→description search passed for the eight-dish fixture while
  preserving an old draft revision. All records were simulated/local.
- In-app browser showed the active eight-dish menu alongside an old salmon draft
  with its original two-item selector and modifiers. An already-delivered smoke
  ticket retained old names/times. After explicit user approval, a fresh localhost
  browser test clicked Confirm and send on a two-unit salmon draft after switching
  the active menu. It passed: one submitted ticket/event, two distinct physical
  units, original menu name/station/typical time retained. Acknowledgment/start/zone
  reservation did not happen prematurely. The earlier automatic approval block is
  resolved. No new broad responsive/accessibility claim is made.
- Default vectors are deterministic **lexical hashing**, not trained semantic AI.
  The opt-in OpenAI semantic adapter has mocked transport coverage only; no paid
  calls/key usage/live quality test occurred. PDF/photo/arbitrary prose extraction
  remains unimplemented. The later in-app upload/review follow-up below adds the
  management screen; API/CLI remain available.
- Runtime menu versions/candidates/indexes remain in-memory; startup JSON supplies
  persistence. Physical ingredient geometry cannot be invented/remapped by menu
  activation. Voice/STT, real CV/UNO Q, live Databricks, auth and deployment retain
  their prior limits. Dependent-lane human review remains outstanding.

## In-app menu upload/review — 2026-11-14

The **Menu setup** screen is now available beside the two service screens and
through **Upload & review a menu** on Server. A demo lead can upload JSON/CSV/TXT
(automatic preparation/encoding), or paste content and choose Prepare & encode.
The preview shows dishes, prices, descriptions, aliases/modifiers, unknown kitchen
fields and matching warnings. A review checkbox and explicit Activate menu action
use the existing Core transaction; old drafts/tickets retain their original menu.

- **113 backend tests passed** in the cached Python3.11.18 environment. No backend
  schema/provider/dependency change was required for this screen.
- **9 frontend behavior cases passed in Node VM**, covering file auto-encoding,
  review gating, input invalidation, stale menu revisions, role/connectivity,
  session changes during preparation, provider errors, uncertain activation/retry,
  unsupported/oversized files and escaped preview content. CI is configured to run
  these through Node's test runner; this task did not run remote CI.
- Real in-app browser: uploaded the eight-dish JSON through the file chooser,
  observed automatic encoding, reviewed and activated it without API/CLI use.
  An existing salmon draft kept its original choices and the new-order selector
  showed all eight dishes. Pasted CSV review/activation also passed by keyboard
  (Space→Tab→Enter); malformed JSON showed an error while preserving input.
  The preview exposed the intentionally shared `special` alias as a warning.
- Menu setup had no page horizontal overflow at 320, 768 and 1280 CSS pixels;
  keyboard focus on Activate had a visible 3px outline. No browser console errors
  appeared in the final flow. Screen-reader use, actual 200% browser zoom,
  cross-browser/physical phone and live remote semantic providers were not tested.
- Upload text and review state remain in memory; runtime menu changes still reset
  with the backend. PDF/photo extraction, durable storage, production auth and live
  hardware/cloud guarantees remain outside this change. See the
  [upload-screen handoff](handoffs/2026-11-14-menu-upload-review.md).

## PDF/photo and agent integration follow-up — 2026-11-14

Local PDF/PNG/JPEG extraction plus editable dish rows are implemented. Prior
PDF/photo-unavailable notes describe earlier checkpoints; MENU_EXTRACTION owns
current behavior/limits. Agent task map and teammate integration guide are linked
from INDEX and bootstrap. OCR is separate from grouping, correction, encoding and
activation, with no new operational authority or raw-document analytics.

119 backend tests and existing nine UI state checks pass. Python lint/format and
JS syntax pass. Real Apple Vision recognized the synthetic PNG and a generated
one-page scanned PDF (nine proposals, including a logo false positive). Browser
photo upload → remove logo → correct dish name → encode eight items → human
review → activate passed. Linux Poppler/Tesseract and the updated Docker build
were not run; real menus/languages/layouts need further validation. No paid calls.

## Separate Server/Kitchen coordination — 2026-11-14

Implemented and documented both journeys in SERVICE_COORDINATION. Kitchen has a
canonical physical-dish lineup with seat/modifier/request/timing context and
existing start/ready actions. Kitchen staff can publish order-linked coordination
updates to the owning server; recipient/lead explicitly acknowledges/resolves them
without changing food state. Both roles can request a deterministic device summary,
with explicit browser Print and optional Speak/Stop presentation.

- Work delegated into separate backend/frontend clones and reviewed by an Astra
  agent at maximum reasoning. Independent supervision cleared source after fixes
  for unit context, zone-waiting start semantics, timer refresh and keyboard focus.
- **135 backend tests passed**, including 16 new service regressions. Scoped Ruff
  lint and formatting passed across 39 files. **21 UI behavior cases passed** in
  native Node VM (9 existing menu + 12 service); all changed scripts parse. CI is
  configured for Node test execution; no remote CI run is claimed.
- Fresh full-server MVP HTTP smoke passed, preserving existing menu/order/zone/
  partial-ready/retry/fallback/notification/delivery behavior.
- In-app browser with separate kitchen/server sessions passed: kitchen ack/start/
  first-unit ready, targeted partial pickup update, Server Two has no addressed
  update, Server One receives/acknowledges/picks up then resolves. Both roles'
  requested summaries displayed. Old pickup request became non-actionable after
  pickup; one-of-two ready milestone persisted and no all-ready notification fired.
  State changes marked displayed summary stale and disabled stale playback/print.
- Final HTTP verification confirmed update revision3/resolved, remaining unit
  queued, no note text in update events, and no order/dish/event changes from
  summary reads. Final browser console had no error entries.
- Print handler and explicit/cancelable speech are tested with fakes; audible
  output, headphone/earpiece routing and physical printing are unverified. No new
  broad responsive/screen-reader/cross-browser claim or live STT/CV/cloud claim.
- Summary/handling routing is role/session scoped, but global demo snapshots still
  expose operational update notes. This is not private-inbox/production auth.
  In-memory persistence/outbox and one-worker limits remain. No paid service,
  staging, commits, push or publication were performed.

See the unique [integration handoff](handoffs/2026-11-14-service-flow-integration.md)
and its backend/frontend lane handoffs for exact ownership and integration seams.
