# Status — MVP v2 checkpoint, 2026-11-14

[PROJECT_SPEC](../PROJECT_SPEC.md) owns intended behavior; this file owns execution evidence. [Normalized brief](MVP_TEAM_BRIEF.md) is portable team context. The Menu workstream **also owns Core/backend and integration**; personal names remain unassigned. STATUS is not a concurrency lock.

## Final integration snapshot — 2026-11-14

PR #1 merged to main `35d6d08`; main CI passed. UI `dd6886e` arrived during the
final check and is integrated in a follow-up: accessible guarded theme controls
on Server screens, canonical pinned-menu sections/descriptions/quantity badges,
Kitchen forced-dark preserved and all nine upstream changed sources archived.
Frontend **62 passed**. Fixed the release probe's older-snapshot/malformed-mode
crash; **13 probe/auth tests passed**. Astra independently cleared both changes.
See [follow-up handoff](handoffs/2026-11-14-final-ui-and-release-probe.md).

Post-merge hosted probe now reports frontend503 (`Demo access is not configured.`),
old backend health404 and state/OpenAPI200withoutlogin. Proxied state is200but
lacks menu_revision; voice status200alone does not validate this release.
Matching platform secrets and backend publication are still required by the
signed-in deployment owner. Local software acceptance is not hosted readiness.

Final pre-main Deepgram recheck on application source `5b956b1` used four actual
provider streams with synthetic speech: correct Server draft, Kitchen start and
successful clearer Kitchen acknowledgment. The first short acknowledgment
required clarification and preserved food state; tap recovery passed. Total
audio 6.5969375s (usage6.6s), estimated USD0.0008. Initial three-clip script passed
30 assertions including auth, single-use tickets and human-only Confirm.
Focused voice/Core/application/auth regression suite: **96 passed**. Full push
and PR CI on `5b956b1` also passed (365 Python, **55 frontend**, container smoke).
Hygiene passed286indexed paths; 44 locally reachable commits scanned with no
Gitleaks findings. Astra found no must-fix source issue. See
[final Deepgram validation](handoffs/2026-11-14-final-deepgram-validation.md).

Final pull follow-up integrates UI `21cc4a5` and `4d29098` through merges
`ba4e510` and `d6255be`. Kitchen layered surfaces and ticket-grouped physical-zone
panels preserve all configured zones, current assignment/review guards and
unassigned/unknown status. Server depth/hairline tokens are retained; original
upstream HTML is archived unloaded. **55 frontend tests passed** after both
changes; Astra independently passed 25 operator cases and cleared the delta.
Actual local browser verified Kitchen tickets/grouped zones plus Server ordering
menu and My tables/targeted update. No console errors on the checked pages.
The seeded ticket and eight-dish menu remain available. See
[final pull audit](handoffs/2026-11-14-final-pull-audit.md).

Fresh read-only production probe still shows backend health404, missing login
challenge and frontend API proxy404. Hosted publication/verification remains
assigned to the signed-in deployment owner, not completed by this branch.

All currently requested/fetched workstreams are integrated: Menu/service9d3face,
Voice9fcdd95, CV7133aaf and UI163d9e8. They are ancestors of the reviewed
application code commit0c56900. PR: https://github.com/AkashGogate/dig-in/pull/1.

- Exact code-tip Linux CI and PR CI **passed**:245 backend +71 CV +49 legacy
  kitchen = **365Python tests**, **53Node tests**, root Docker build and actual
  container HTTP/CV-contract smoke. See
  [push CI](https://github.com/AkashGogate/dig-in/actions/runs/43662231728) and
  [PR CI](https://github.com/AkashGogate/dig-in/actions/runs/43662236456).
- Final CV reconnect guards preserve calibrated background, invalidate dwell on
  reconciliation, reject stale buffered frames and ambiguous devices, fail health
  immediately and keep canonical adaptation off. Synthetic subprocess/video tests
  run without opening cameras. Darwin-only PyObjC dependencies/lock validated.
- Latest Kitchen glance layout preserves the teammate stylesheet, chronological
  sent-ticket order, physical-unit actions/counts, review-aware ready accent and
  stable disclosure focus. Full frontend53cases pass. Final Kitchen layout was inspected in the real local
  browser with actual ticket/physical-unit data; protected3page browser flow is recorded below. No fake UI authority or camera feed was reintroduced.
- Hygiene passed282indexed paths; all38commits scanned with Gitleaks8.30.1,
  no findings. Actual backend/.env remains ignored/undisplayed; calibration tip
  contains only.gitkeep. Main and teammate branches were preserved.
- Real voice evidence remains102synthetic provider cases:66expected behavior,
  36safelyflagged,0silentlywrong, plus9fixed cases;246.518s, estimatedUSD0.0316.
  Separate1.82s v2stream produced only a draft, estimatedUSD0.0002. No further
  paid calls were needed for the last UI/CV changes.

The user assigned actual Fly/Vercel republishing to another signed-in agent.
CLI tools were installed, pending sign-ins canceled, and **no production change**
was made here. The local demo uses real shared API state with labeled simulated
voice/camera inputs. [Acceptance map](INTEGRATION_ACCEPTANCE.md) and
[deployment handoff](DEPLOYMENT_HANDOFF.md) distinguish completed software from
hosted release, physical rig/mic/phone/printer and cloud validation still needed.

## Fresh local end-to-end acceptance — 2026-11-14

All **24 real HTTP acceptance checks passed** across draft review/confirmation,
retry protection, physical-unit allocation, CV evidence guards, partial/all-ready
notifications, targeted staff updates, read-only summaries, pickup and delivery.
The actual browser PDF flow passed extraction → correction → local encoding →
explicit review → activation. Readable photo OCR returned HTTP 200. Replacement
menu voice matching and pinned historical menu snapshots passed; the original
eight-dish active menu and seeded demo ticket were preserved/restored.

No blocking defect was found in these exercised local paths. This pass used
simulated voice/CV and no additional paid services; hosted release and physical
device checks remain assigned to the deployment owner. See the
[end-to-end acceptance handoff](handoffs/2026-11-14-end-to-end-demo-acceptance.md).

## Earlier incremental evidence

## Latest pushed workstreams integrated — 2026-11-14

Source now includes Voice9fcdd95, CV7e13c16 and UIabe9fb1 on top of the Menu/service
checkpoint, with real merge ancestry. Astra maximum reasoning supervised the
incremental merge and the bounded evaluation work. The prior checkpoint below is
historical and is superseded by these results.

- **245 backend +55 CV +49 legacy kitchen tests passed;48 Node22 tests passed.**
  Ruff lint/format passed across62 scoped Python files. Native middleware entrypoint,
  shared-client/auth/retry tests and actual ASGI composition are included.
- Real Deepgram v2 WebSocket probe:1.82s synthetic audio, expected dish matched,
  conservative confidence0.8691406, editable draft only; estimatedUSD0.0002.
  Full prerecorded matrix:102 audio cases across6 synthetic voice/noise personas,
  exact246.518375s audio, estimatedUSD0.0316 at configuredrate. **66 matched
  expected behavior,36 were safely flagged,0 silently wrong outcomes** under the
  harness. Nine fixed controlled/historical cases yielded111total:67exact,
  44flagged,0wrong, safetygatePASS. MOCK26:18exact/8flagged/0wrong, gatePASS.
  This is scripted speech/noise stress testing, not real staff/room accuracy.
- Shared final-word minimum confidence protects low critical words; any unknown
  segment stays unknown. Known live low/unknown confidence requires whole-draft
  Server review or Kitchen clarification. Threshold0.6 remains provisional.
  Eval uses the same confidence path; exact sample-duration caps and invalid audio
  checks precede paid calls. Historical reports remain unchanged/labeled; routine
  raw synthetic reports/audio stay ignored locally.
- Shape-based CV increment preserved with same-frame detector agreement,
  ambiguous-footprint/hand/confidence gates and canonical rebaseline disabled.
  Legacy active-ticket advancement remains isolated from canonical Restaurant.
- New Take orders/My tables/Kitchen operator pages use canonical /api/v2 only.
  Prototype snippets are retained as unloaded reference, never fallback state.
  Pinned menus, exact retry, per-tab verified login, per-unit actions, recipient
  updates and explicit summaries are connected. Full voice/OCR/activation,
  reconciliation and device print/speech remain linked in the original workbench.
- Browser on the final protected local app passed all3newpages:401→verified tab
  login→Server draft/save r2→separate human Confirm→Kitchen acknowledgment and
  distinct A/B units→one start/manual-ready→targeted pickup message→Server update
  acknowledgment without food change→exact pickup/release→fresh summary with
  1of2 cumulative ready,1picked up,0currentlyready. Authenticated HTTP smoke passed.
- First remote Linux CI built the root container and passed test suites. Its final
  route-introspection assertion failed on FastAPI's _IncludedRouter; replaced
  with an actual HTTP health/CV-route probe plus owning producer-contract import.
  Final CI result is recorded below when available.
- Secret hygiene passed273indexed paths before final docs; staged and all-ref
  history scans found no secrets. Actual credentials were read from ignored
  backend/.env without displaying values; permissions restricted to owner access.
  Main and teammate branches are preserved. Integration source is published only
  on codex/application-integration; no production deployment is claimed.

**Remaining live release gaps:** deployed frontend still has no login gate/API
proxy, backend health404 and state200withoutlogin. Authenticated frontend API is
also404. Local credentials work for the real provider, but no Fly/Vercel deployment
credentials were supplied; deployment wiring/secrets and hosted browser/proxy/WS/
8MiB upload checks remain. No physical CV rig/model/calibration, microphone/phone,
headphone/real printer, live Databricks, durable state or multi-machine validation.
The36flagged live audio cases require correction/review. A passed safety gate is
not a guarantee of perfect recognition or a failure-free demo.

See [deployment](DEPLOYMENT.md), [UI handoff](handoffs/2026-11-14-ui-application-integration.md),
[Voice increment](handoffs/2026-11-14-voice-increment-integration.md),
[CV increment](handoffs/2026-11-14-cv-increment-integration.md) and
[eval provenance](../backend/eval/dig_in/runs/README.md).

## Earlier application integration checkpoint — 2026-11-14

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
