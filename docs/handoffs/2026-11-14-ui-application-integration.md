# UI incremental application integration — 2026-11-14

## Claim and ancestry

- Agent lane: service_frontend; isolated clone `/private/tmp/dig-in-ui-application-20261114`, branch `codex/ui-application-integration`.
- Base combined application checkpoint: `d5646f5`.
- Incoming actual Git UI ref: `abe9fb1de0493948db7303b5551f03266f33d584`, fetched from root clone into `refs/remotes/team/UI` and ancestry-merged with `--no-commit --no-ff` for review. No commit, push, deployment or paid provider call in this lane.
- Only merge conflict: `.gitignore`. Its working content preserves base HEAD exactly; index remains pending/unresolved intentionally because root owns the actual ancestry merge. Root should keep its complete current ignore policy.

## Result

The incoming standalone UI is now three real operator pages using the shared `/api/v2` Menu/Core. Incoming visual tokens remain unchanged in `style.css`, page CSS is retained, and all eight original incoming executable/doc sources are preserved byte-for-byte as unloaded `.txt` reference in `frontend/prototypes/ui-abe9fb1/`. Their fake state/API/microphone/feed/realtime/undo behavior is not executed. `server-alert.js` contains an explicit no-auto-output seam.

`data.js` provides injectable transport and in-memory identity/access, current snapshots, exact indeterminate retry and explicit read-only summaries. Hosted empty HTTP origin remains same-origin. A real 401, including plaintext HTTP Basic challenges, reveals per-tab access verification. Credentials never leave closure memory except the Authorization header and are not exposed by client context or persisted. Successful snapshot verification is required before claiming sign-in. Native cached browser Basic still works without prompting again.

`operator-pages.js` renders:

- Server manual composer: configured tables/seats, pinned menu, stable line IDs, quantity/modifier IDs/guest notes, Start → Save draft → separate human Confirm of the clean saved revision. Unknown/table/dietary flags remain blocking pending explicit review; unattached notes require a saved target line. Root’s incremental Voice low-confidence flag has an explicit `reviewed_speech` action. New pages link the full existing workbench for microphone capture, complete review, menu OCR/encoding/activation and camera/stock recovery.
- Server own tickets: exact physical-unit pickup, optional whole-ticket delivered close-out, recipient-scoped structured kitchen updates with separate acknowledgment/resolution, and on-demand displayed summaries. Historical pickup requests show current ready-unit counts.
- Kitchen: canonical per-unit ticket lineup, station filter, distinct acknowledgment/start/manual-ready, full modifiers/seat/guest context, unknown timing labels, actual physical zones/review status and separate recipe expectation/accepted balance reference. Structured updates target the ticket’s server via Core, never editable sender/recipient fields.

Dirty composer text and staff-authored note/kind/open panel survive polling. Busy mutations prevent stale GET overwrite, exact retry blocks new changes/session switching, summaries discard late actor responses and mark relevant state changes stale. Unchanged polls advance elapsed time without replacing focused controls. No percentages, fabricated stage timestamps, fake camera/mic status, browser restaurant persistence, automatic speech/chimes/vibration or UI-only food completion.

## Frozen copy paths

Copy these exact paths from this clone into root’s actual UI ancestry merge:

```
frontend/data.js
frontend/operator-pages.js
frontend/operator.css
frontend/server-alert.js
frontend/server-order.html
frontend/server-tables.html
frontend/kitchen.html
frontend/style.css
frontend/INTEGRATION.md
frontend/README.md
frontend/UI_PLAN.md
frontend/tests/operator-pages.test.cjs
frontend/prototypes/ui-abe9fb1/README.md
frontend/prototypes/ui-abe9fb1/data.js.txt
frontend/prototypes/ui-abe9fb1/server-alert.js.txt
frontend/prototypes/ui-abe9fb1/server-order.html.txt
frontend/prototypes/ui-abe9fb1/server-tables.html.txt
frontend/prototypes/ui-abe9fb1/kitchen.html.txt
frontend/prototypes/ui-abe9fb1/INTEGRATION.md.txt
frontend/prototypes/ui-abe9fb1/README.md.txt
frontend/prototypes/ui-abe9fb1/UI_PLAN.md.txt
docs/handoffs/2026-11-14-ui-application-integration.md
```

No `app.js`, `index.html`, config, backend/shared contract or shared root docs edits in this lane. Root adds navigation from default index to the three operator pages and adds new-script syntax checks to CI. Existing test glob already includes `operator-pages.test.cjs`. A temporary `frontend/node_modules` symlink to root’s installed dependency directory was used for test execution and removed before freeze; no dependencies or generated files are part of the copy.

## Checks and evidence

- Native Node22 `/private/tmp/dig-in-submission-tools/node-v22.23.5-darwin-arm64/bin/node` syntax checks passed for `data.js`, `operator-pages.js`, `server-alert.js`.
- Full existing + new frontend test suite: **47/47 passed**, including **18 new operator client/DOM tests**. Initial missing-local-dependency failure was resolved using root’s existing installed `@vercel/functions`; no dependency contract changed.
- Astra independently ran the **18/18** new operator checks and cleared final source review: plaintext401, serialized verified auth, stale GET gate, authored-note preservation, explicit confidence review, unit/zone/seat context and unknown-start labels. No remaining merge-blocking source finding reported.
- Actual canonical FastAPI router TestClient smoke passed: start draft, save canonical menu ID/modifier/request/seat with quantity two, separate Confirm current revision, Kitchen acknowledgment assigning two distinct physical zones, start and manually ready one exact unit, publish pickup request to owner, recipient-scoped summaries, acknowledgment without changing food, then exact unit pickup.
- `git diff --check` passed. Original source archives compared to actual incoming UI ref before freeze.

## Limits and root follow-up

- Browser/layout/live-endpoint verification remains root integration evidence. Dependency-free DOM tests intentionally do not claim browser rendering, hardware microphone/camera, speech output or deployed auth success.
- Page navigation intentionally requires staff reselection; saved backend drafts/tickets remain. Credentials remain tab-memory only; another page may need the explicit auth fallback when cached browser Basic is unavailable.
- Delivery preference is visibly disabled because there is no canonical stored field. Floor positioning, other-server guest detail, per-dish served state, courses/helper/priority queues, automatic voice/feed/realtime mock and undo remain unavailable.
- Summaries in new pages display text only; explicit browser Print/Speak/Stop stays in the existing workbench. Device/browser speech does not guarantee headphones.
- Root owns default navigation, complete incremental Voice/backend merge, CI script additions, deployment/prototype archive output policy and final browser verification. Existing integration scaffold, menu/import/embedding seams, pinned snapshots and canonical events/outbox are preserved and remain navigable for future agent contributions.
