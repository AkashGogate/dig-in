# V2 operational, menu and event contracts

New work uses `/api/v2`. Sources: [`mvp/contracts.py`](../backend/app/mvp/contracts.py) for commands/state; [`mvp/menu.py`](../backend/app/mvp/menu.py) for MenuDocument/items/modifiers; [`analytics/events.py`](../backend/app/analytics/events.py) for CanonicalEvent. Generated schemas at [v2 contracts](http://localhost:8000/api/v2/contracts) and [OpenAPI](http://localhost:8000/openapi.json) are authoritative; no lane independently redefines shapes.

| Endpoint | Meaning |
| --- | --- |
| `POST /api/v2/sessions` | `{actor_id}`→session_id/actor; simulated device/staff identity |
| `GET /api/v2/service/summary?audience=server\|kitchen` | Demo-session/role-scoped read-only summary of current lineup, orders and update actionability; not retained/exported |
| `GET /api/v2/state` | Shared snapshot, physical zones/cameras/progress/stock/export health |
| `POST /api/v2/commands` | Validated command, `X-Demo-Session` header; returns result/state/replayed |
| `GET /api/v2/contracts` | Command/state/canonical event JSON Schemas |
| `GET /api/v2/menu`, `POST /menu/match` | Canonical configured menu and deterministic candidate/flag matcher |
| `POST /api/v2/menu/extract`, `GET /api/v2/menu/extraction-status` | Lead-only bounded PDF/PNG/JPEG → provisional editable dishes; readiness/limits. No encoding/activation side effect |
| `POST /api/v2/menu/prepare` | Lead session: normalize/validate/index structured menu candidate; no activation |
| `GET /api/v2/menu/index`, `POST /api/v2/menu/search` | Current index metadata / explicit candidate retrieval; search requires demo session |
| `GET /api/v2/menu/import-status`, `/voice/status` | Explicit adapter-only importer and mock transcript availability |
| `GET /api/v2/events?format=jsonl` | Canonical accepted/observed log, original IDs/source times preserved |
| `POST /api/v2/events` | Supported canonical adapter **intent**, translated/validated by Core, never arbitrary fact insertion |
| `GET /api/v2/analytics/health`, `/analytics/pending` | Retry health/exact pending rows; not live cloud dashboard |

Use the actual shared backend host instead of localhost. Domain conflicts are409; invalid schemas are422. Demo actor/device identity is not production authentication. Source fields describe provenance, not independent proof a trusted device/human acted.

## Command and identity

Command v2 contains `event_id`, `schema_version:2`, source (`tap|voice|camera|system`), timezone-aware `time`, optional device/run IDs, simulation label, and action-discriminated payload. Keep the **exact serialized envelope including time** on retry; changed content/identity under an existing ID is rejected. Distinct actions need new IDs. Idempotency lasts only this in-memory process.

```json
{
  "schema_version": 2,
  "event_id": "demo-order-start-001",
  "source": "tap",
  "time": "2026-11-14T20:00:00Z",
  "device_id": "demo-phone-1",
  "run_id": "interactive-demo",
  "simulated": true,
  "payload": {"action": "start_order", "table_id": "1"}
}
```

Core takes actor/role from the demo session. Device identifiers are honest simulated provenance, never diarization. Only current-revision tap `confirm_send` with `human_confirmed:true` and no unresolved flags submits. Capture text is ephemeral input, not retained/exported event payload.

| Domain | Actions / safeguards |
| --- | --- |
| Menu | activate_menu; lead/tap/human review + expected active revision, exact-envelope retries |
| Staff coordination | publish_service_update (kitchen/lead tap, order-derived recipient); acknowledge_service_update/resolve_service_update (recipient/lead tap, current update revision). No food transition |
| Draft | start_order, edit_draft, capture_voice, resolve_flag, confirm_send; stable line IDs/revision, unknown/mismatch review, mandatory human tap |
| Kitchen/order | acknowledge, retry_zones, deliver_order; acknowledgment separate from start; all-K zone capacity/FIFO; delivered optional after pickups |
| Physical dish | start_dish, ready_dish, pickup_dish; timestamps, one unit/zone; camera uses evidence rather than bypassing commands |
| Camera | camera_status, zone_observation, reconcile_zone; occupancy/unknown, stable_ms/no hand, assignment version and source-time checks |
| Constrained speech | kitchen_voice; menu parser plus authoritative order/unit ambiguity checks, not freeform speaker auth |
| Ingredient | stock_observation, accept_stock; reviewed countable movement/provenance, no recipe double deduction |

## Menu and correction counts

Menu item IDs/names/aliases/modifier IDs drive all new paths. Optional station/call-out/typical_minutes/recipe/ingredient mapping remain null if unknown. Orders snapshot name/kitchen fields. Reviewed JSON loads through DIG_IN_MENU_PATH. [MENU_PIPELINE](MENU_PIPELINE.md) documents JSON/CSV/item-per-line preparation, automatic local/optional semantic vectors and explicit reviewed activation. PDF/PNG/JPEG extraction produces correctable provisional dishes via local OCR; see MENU_EXTRACTION. Future model extractors can replace that seam. State includes current `menu_revision` and a `menus` map keyed by content revision; orders pin their revision at draft creation. Item descriptions/categories and snapshotted modifier labels are additive fields. Both original fixtures and the eight-dish DIG IN fixture load without code changes.

`corrected_draft_lines` compares the latest voice baseline and final reviewed lines by stable ID and menu_id/quantity/modifiers/seat/requests: distinct changed/added/removed IDs count once; reverting to baseline counts zero. `initial_voice_draft_line_count`, final_line_count and capture_mode define denominators/context. Additions can make count exceed baseline; do not call this recognition accuracy or edit-tap count. Pure manual capture has no voice baseline.

## Canonical events and accepted facts

CanonicalEvent retains event_id, nullable order_id/dish_id, dotted type, tap/voice/camera/system source, actor, source time and structured payload. V2 adds received_at, run_id, simulated and `outcome:accepted|observed`. Original time/identity survive export; receipt time never replaces source time. The canonical vocabulary includes the brief’s submitted/acknowledged/zones assigned/waiting/dish started/ready/picked_up/order ready/delivered/zone unexpected/camera status/stock changed, plus aggregate order.picked_up and explicit draft/observation/clarification/reconciliation/retry facts declared alongside the model.

Incoming camera `dish.ready` intent still needs current zone/version/stability/no-hand evidence. Rejected/stale input does not become an accepted milestone. Ignored evidence emits an observed camera.observation; raw stock evidence emits stock.observation, and only accepted review emits stock.changed. Derived system facts get deterministic related IDs. Local state/event/outbox commit is coordinated; sink I/O is background, and failures remain pending. No raw transcripts/audio/video in canonical payloads. See [analytics mapping/SQL](../analytics/README.md).

## Explicit v1 compatibility boundary

`/api/v1` + `coordination-v1.html` retain the prior broad scaffold with **separate state**; the original legacy.html WebSocket voice lab is separate again. They are preservation surfaces, not a second MVP authority. No automatic migration or dual-write exists. Schema version changes are intentional because allocation/readiness/draft semantics changed.

| Earlier concept | Current v2 meaning |
| --- | --- |
| manual source | tap |
| mock_camera | camera with simulated:true |
| id + occurred_at | event_id + time; preserve identity/time explicitly when preparing an intentional import |
| command/observation envelope kind | canonical outcome distinguishes accepted fact vs observed evidence after Core validation |
| batch bay/course assigned on send | one dish unit/zone, all K atomically on acknowledgment; courses deferred |
| staff-ready default/optional camera experiment | ready-only zone convention and stable occupancy default; tap fallback |
| speech supplement-only draft | deliberate menu-constrained editable capture; human Confirm gate retained |
| per-dish running task/helper/priority | Canonical dish lineup plus bounded v2 coordination updates/summaries; independent v1 task/helper/priority state stays deferred/isolated |

The mapping describes semantics, not a working legacy importer. Never silently relabel old/rejected observations as accepted facts. Menu/Core coordinates any future version/migration and dependent review; preserve stable examples/fixtures and tests.


## Service handoff contract

`service_contracts.py` owns ServiceUpdate/ServiceSummary and update commands. State
adds `service_updates`; `/contracts` exposes `service_summary` alongside existing
shapes. Update kinds are delay, needs_attention, pickup_request and availability;
explicit typed notes are at most 300 characters. IDs/source time/outcome survive
canonical events; authored note text and generated summaries are not analytics
payloads. Pickup requests require an actual currently ready physical unit, and
summary projections re-evaluate actionability after pickup. Receiving/handling an
update never changes cooking, zones or pickup state. Summary reads emit no event.

Summary/handling routing is role/session scoped, while existing global demo state
and command response snapshots are not a confidentiality boundary. See
[SERVICE_COORDINATION](SERVICE_COORDINATION.md) for both journeys and audio limits.


## Application composition additions

Full-server HTTP uses demo Basic authentication outside explicit local mode,
including data, commands, contracts and adapter routes. `/healthz` is the sole
minimal public health route. See DEPLOYMENT for matching Fly/Vercel secret config.
Demo actor/device sessions remain required for commands and role-scoped summaries;
shared snapshots are not a private per-role confidentiality boundary.

Voice: `/api/v2/voice/ticket` requires authenticated demo session plus optional
`{order_id,menu_revision}` (server) or `{menu_revision}` (kitchen). Ticket pins the
server-held menu, expires, is single-use and requires matching WS session_id.
`/api/v2/voice/stream` consumes paced mono PCM16 at16kHz; status/usage expose mode
and bounded in-memory estimates. Provider errors leave text/manual fallback.

CV: `/api/v2/cv/context` and `/api/v2/cv/observations` require cook/lead session
inside the HTTP gate. Producer schema remains cv-service/cvsvc/events.py and
schema/events.schema.json. Envelope `{event,run_id,simulated,binding?,evidence?}`
requires capture-time unit/version correlation and measured stable/no-hand evidence
for operational occupancy. Ingredient/legacy unbound evidence requires review,
never recipe deduction. See cv-service/V2_INTEGRATION.md and executable models in
cv_bridge.py for exact shapes/freshness/confidence/retry/recovery semantics.
