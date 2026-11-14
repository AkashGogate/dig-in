# V2 operational, menu and event contracts

New work uses `/api/v2`. Sources: [`mvp/contracts.py`](../backend/app/mvp/contracts.py) for commands/state; [`mvp/menu.py`](../backend/app/mvp/menu.py) for MenuDocument/items/modifiers; [`analytics/events.py`](../backend/app/analytics/events.py) for CanonicalEvent. Generated schemas at [v2 contracts](http://localhost:8000/api/v2/contracts) and [OpenAPI](http://localhost:8000/openapi.json) are authoritative; no lane independently redefines shapes.

| Endpoint | Meaning |
| --- | --- |
| `POST /api/v2/sessions` | `{actor_id}`→session_id/actor; simulated device/staff identity |
| `GET /api/v2/state` | Shared snapshot, physical zones/cameras/progress/stock/export health |
| `POST /api/v2/commands` | Validated command, `X-Demo-Session` header; returns result/state/replayed |
| `GET /api/v2/contracts` | Command/state/canonical event JSON Schemas |
| `GET /api/v2/menu`, `POST /menu/match` | Canonical configured menu and deterministic candidate/flag matcher |
| `GET /api/v2/menu/import-status`, `/voice/status` | Explicit adapter-only importer; voice mode (`mock_transcript` or `deepgram_stream`) and whether the demo password is required |
| `POST /api/v2/voice/ticket` | Demo password (when configured); 503 if live voice is off, 429 if a spend cap is hit; returns a single-use ticket valid 30s and the max stream seconds |
| `WS /api/v2/voice/stream?ticket=` | Browser sends WebM/Opus chunks then `{"type":"stop"}`; server relays `interim`/`final`/`done` text (plus `limit`/`error`). Audio is forwarded and dropped; text is never stored. The browser then sends the text through `capture_voice` (`capture_mode: live_voice`) or `kitchen_voice` like typed text |
| `GET /api/v2/voice/usage` | Demo password; audio seconds used/remaining, streams started/rejected, estimated USD (in memory, resets on restart) |
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
| Draft | start_order, edit_draft, capture_voice, resolve_flag, confirm_send; stable line IDs/revision, unknown/mismatch review, mandatory human tap |
| Kitchen/order | acknowledge, retry_zones, deliver_order; acknowledgment separate from start; all-K zone capacity/FIFO; delivered optional after pickups |
| Physical dish | start_dish, ready_dish, pickup_dish; timestamps, one unit/zone; camera uses evidence rather than bypassing commands |
| Camera | camera_status, zone_observation, reconcile_zone; occupancy/unknown, stable_ms/no hand, assignment version and source-time checks |
| Constrained speech | kitchen_voice; menu parser plus authoritative order/unit ambiguity checks, not freeform speaker auth |
| Ingredient | stock_observation, accept_stock; reviewed countable movement/provenance, no recipe double deduction |

## Menu and correction counts

Menu item IDs/names/aliases/modifier IDs drive all new paths. Optional station/call-out/typical_minutes/recipe/ingredient mapping remain null if unknown. Orders snapshot name/kitchen fields. Reviewed JSON loads through DIG_IN_MENU_PATH; arbitrary photo/PDF/model import is a protocol/status stub. Second fixture loads without code changes.

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
| per-dish running task/helper/priority | deferred; partial count + once-only all-ready notification |

The mapping describes semantics, not a working legacy importer. Never silently relabel old/rejected observations as accepted facts. Menu/Core coordinates any future version/migration and dependent review; preserve stable examples/fixtures and tests.
