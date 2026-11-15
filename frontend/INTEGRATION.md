# UI integration contracts

These pages consume the same Menu/Core authority as `index.html`. There is no mock fallback and no `/orders` or `/dishes` alternative API. A transport failure never means success.

## Files and seams

- `style.css` is the incoming UI branch’s unchanged design tokens/component source. Page-specific visual CSS is retained in each page; `operator.css` adds shared responsive operator layout, focus and form styling.
- `data.js` defines `DigInOperator.createClient`: injectable HTTP transport, one in-memory actor/session, snapshot reads, deterministic uncertain-command retry and explicit read-only summary requests. Do not add restaurant persistence, fabricated feed states or legacy endpoint fallbacks here.
- `operator-pages.js` owns presentation and delegated controls for three actual HTML pages. Kitchen lineup is a projection of canonical `Dish` records. It is not a second task/cooking machine. The manual editor copies `LineInput` fields only and always carries stable line IDs and the saved revision.
- `operator-pages.test.cjs` executes the production client and delegated page handlers with controlled responses. It covers pinned menus, actor scopes, save/Confirm separation, current physical assignments, authored notes, polling, escaped content, summaries, credentials and exact retry.
- `server-alert.js` intentionally contains no automatic sound, vibration or bulk pickup behavior. Prototype implementation remains in the archive. Integrated pages display scoped updates and current ready units.
- `index.html` and its existing modules remain the complete workbench for microphone capture, menu document extraction/activation, zone reconciliation, stock observation acceptance and explicit device print/speech. Link to those functions instead of recreating unreviewed adapters.

## Read contracts

`GET /api/v2/state` returns the demo snapshot. It is intentionally global; this endpoint is not a privacy/auth boundary. New Server views filter ticket ownership and update recipient IDs; Kitchen views include non-draft tickets. Command permissions and summary recipient scopes are enforced by Core.

`state.tables` defines valid tables and seats. Never manufacture tables 1–20 or zone identifiers derived from table/seat. `state.zones` supplies actual physical IDs, assignment versions, occupancy and review requirements. Keep historical dish `zone_id` provenance separate from current `zone.dish_id` assignments.

A draft selects `state.menus[order.menu_revision]`. Do not substitute the latest menu if its pinned revision is missing. Missing price, station, recipe and typical minutes remain unknown. Quantities create physical dish units only on submission. Kitchen displays per-unit ID, line ID, seat, canonical modifier labels and guest request text.

## Identity, access and command contracts

1. `POST /api/v2/sessions {actor_id}` returns `session_id` plus the backend actor. Server pages offer server/lead roles; Kitchen offers cook/lead. This is simulated device/staff selection, not speaker recognition or production identity.
2. Every mutation uses `POST /api/v2/commands` and `X-Demo-Session`. The envelope includes `schema_version:2`, stable `event_id`, source `tap`, original timestamp, run ID and `simulated:true`.
3. Manual composer: `start_order {table_id}`, then `edit_draft {order_id,revision,table_id,lines}`. Each line has `id,menu_id,quantity,modifiers:ID[],seat,requests`. Save does not submit. Unsaved changes and review flags disable human `confirm_send {order_id,revision,human_confirmed:true}`. Stale revisions reject rather than auto-rebase or silently confirm.
4. Unknown/table/dietary flags require explicit review. Unattached dietary notes require a selected saved line; no note is discarded on removing its dish. The root incremental Voice contract’s `low_confidence` flag requires explicit `reviewed_speech`; the full workbench provides capture and complete review context.
5. Kitchen/order operations use canonical `acknowledge`, `start_dish`, `ready_dish`; Server uses `pickup_dish` and whole-ticket `deliver_order`. Acknowledge atomically reserves zones where available; acknowledged queued units may start while waiting. Manual ready requires acknowledgment/current zone assignment/no zone review, and never claims a camera identified food or doneness. Pickup targets one exact ready unit. Delivered is a whole-ticket optional close-out.
6. An indeterminate POST retains the exact serialized envelope and its original session. New mutations and session switching stay blocked until Retry resolves it. Explicit HTTP rejection clears uncertainty and requires fresh review. GETs cannot overwrite an in-flight/just-accepted mutation with an older response.
7. Access credentials, if needed, are stored only in the current JS closure and attached as Basic headers. An actual 401 reveals the form; successful snapshot verification is required before announcing access. No credentials, audio, raw capture transcripts or restaurant state are written to browser storage.

## Kitchen → Server handoff

`publish_service_update {order_id,kind,note}` supports `delay`, `needs_attention`, `pickup_request`, `availability`. Notes are explicitly staff-authored, bounded at 300 characters, escaped when rendered, retained locally while editing, and targeted by Core to the order’s owner. Sender/recipient are not editable UI fields. Submitted/acknowledged/cooking/ready remain separate from update status.

Recipients acknowledge then resolve using `{update_id,revision}` through `acknowledge_service_update` / `resolve_service_update`. These never cook food or mark it ready. Historical unresolved pickup requests display the current ready-unit count and say when no units remain ready.

`GET /api/v2/service/summary?audience=server|kitchen` with the current session is explicit and side-effect free. Display generation time and mark the result stale when relevant order/dish/zone/update state changes. Ignore responses after session changes. New pages display text only; the full workbench owns explicit Print/Speak/Stop and cancels stale speech. No output route guarantees headphones.

## UI state and future contributions

The UI21cc4a5/4d29098 follow-up preserves upstream layered surfaces and shared
depth tokens. Kitchen zone panels group exact current ticket IDs (including
separate tickets at one table), followed by unassigned physical zones. They show
every configured zone regardless of station filter. Ready styling/counts require
matching current assignment and no review flag. The full incoming HTML sources
are retained unloaded in `prototype-reference/`; canonical handlers remain in
`operator-pages.js`.

Local draft edits are unsaved UI proposals, not accepted restaurant state. Polls preserve dirty composer text and active controls. Staff-authored kitchen note/kind/open state is retained per ticket until accepted, explicitly discarded or session change. Unchanged polls advance elapsed labels without replacing controls; timers show elapsed/known typical time, never percentage cooked.

Use the archive for visual/snippet reference only; all original source is retained byte-for-byte as `.txt`. Its simulated microphone/feed, fabricated staff, mock order mutation, undo and mock realtime generator must never be loaded into the integrated app. Root Git ancestry also preserves the original UI commit.

Before promoting a prototype feature, add a canonical contract, Core role/revision/idempotency behavior, focused UI behavior tests, then actual backend/browser verification. Delivery preferences, courses, per-dish served state, floor positioning, helpers/priority queues and continuous listening remain unavailable. Keep them disabled or omit controls; do not create UI-only completion state.
