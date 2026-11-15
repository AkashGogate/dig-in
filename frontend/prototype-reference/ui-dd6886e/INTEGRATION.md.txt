# Frontend integration guide

How the three operator screens get their data, and how to connect them to a real
backend. Written for an agent doing integration work. Pair this with
[README.md](README.md) (per-file overview).

**TL;DR:** every screen talks only to `data.js` — the `api.*` methods and the
`on(event, cb)` event bus. Today `data.js` returns mock data and drives its own
realtime timeline. To go live you (a) flip one flag, (b) implement the REST/WS the
`api.*` methods already call, **or** (c) write a thin adapter that turns the existing
voice backend's WebSocket messages into `bus.*` calls. You never touch the screens.

---

## 1. The one toggle

```js
// data.js
const USE_REAL_API = false;                       // flip to true to hit the network
const API_BASE = window.KITCHEN_COPILOT_API        // set in config.js
              || 'http://localhost:8000';
```

While `false`, `_get/_post/_patch` short-circuit to `null` and every `api.*` method
falls back to in-memory mock state. While `true`, each method tries its HTTP path
first and only falls back if the request fails or returns null. Set the backend URL
in `config.js`, not in code.

---

## 2. The architecture seam (read this before wiring)

State changes flow through **one path**, so real and simulated events are
indistinguishable to the UI:

```
caller ──▶ bus.<applier>()  ──▶  mutate _mock state  ──▶  _emit('event', payload)
                                                              │
                                        screens' on('event', cb) ──▶ re-render
```

- `bus.*` appliers (in `data.js`) are the **only** place state mutates + emits.
- The mock realtime timeline (`startMockRealtime`) and the demo simulators
  (`api.sim.*`) both call `bus.*` — no separate code path.
- **An integration adapter should also call `bus.*`** (exposed as `api._bus`). That
  is the cleanest way to feed real events in without rewriting screens.

---

## 3. `api.*` surface

Read methods fall back to mock; write methods also update mock state and emit.

| Method | HTTP it tries (when `USE_REAL_API`) | Returns / effect |
|--------|--------------------------------------|------------------|
| `getServer()` | — (local) | `{ id, name }` of the signed-in server |
| `getMenu()` | `GET /menu` | `[MenuItem]` |
| `getTables()` | `GET /tables` | `[number]` (defaults 1–20) |
| `submitOrder(payload)` | `POST /orders` | creates + returns an `Order`, emits `order_submitted` |
| `getMyOrders(serverId)` | `GET /orders?server_id=` | `[Order]` for that server |
| `getKitchenQueue()` | `GET /orders` | `[Order]` (all) |
| `getHeardOrders()` | — (mock) | `[HeardOrder]` awaiting line confirmation |
| `confirmHeardOrder(id)` | `POST /heard/{id}/confirm` | removes it, emits `heard_confirmed` |
| `markPickedUp(dishId)` | `PATCH /dishes/{id}` `{status:'picked_up'}` | emits `dish_update` |
| `markServed(dishId)` | `PATCH /dishes/{id}` `{status:'served'}` | emits `dish_update` |
| `markDishReady(dishId)` | `PATCH /dishes/{id}` `{status:'ready',source:'tapped'}` | then `bus.plateReady(id,'tapped')` |
| `getIngredients()` | `GET /ingredients` | `[Ingredient]` |
| `getMicStatus()` / `getCameraStatus()` | — (local) | device status string |
| `getTranscript()` / `getLastHeard()` / `getClarifications()` | — (local) | current voice/camera state |
| `acceptVoiceItem(item)` | — | emits `voice_item_accepted` |
| `resolveClarification(id)` | — | `bus.resolveClarification` |
| `undoLastHeard(id)` | — | `bus.undoLastHeard` |
| `api._bus` | — | the appliers (for adapters, see §6) |
| `api._mock` | — | raw mock state (timers, tests) |
| `api.sim.*` | — | event simulators for manual testing (all route through `bus.*`) |

---

## 4. Event bus

Subscribe with `on('name', cb)`; `cb` receives the payload below. (Emit internally
with `_emit`.) Screens never emit directly — they call `api.*`/`bus.*`.

| Event | Payload | Emitted when |
|-------|---------|--------------|
| `voice_transcript` | `{ text, mic_status }` | a spoken line was transcribed (Take Order shows it) |
| `voice_item` | `{ name, seat, qty, modifiers? }` | voice parsed an order item → appears dashed-blue pending Accept |
| `voice_item_accepted` | the accepted item | server tapped Accept |
| `mic_status` | `'listening'｜'paused'｜'processing'｜'offline'` | mic device state changed |
| `camera_status` | `'live'｜'offline'` | camera device state changed |
| `heard_order` | `HeardOrder` | head chef called an order to the line (dashed-blue ticket) |
| `heard_confirmed` | `heardId` | line confirmed a heard order |
| `dish_update` | `{ dish, order }` | any dish status change |
| `dish_ready` | `{ dish, order, source }` | a dish became ready (`source` `'camera'｜'tapped'`) |
| `server_alert` | `{ table, order_id, zones, zone_range?, dishes, all_ready }` | food is ready to pick up → banner + chime + vibrate |
| `last_heard` | `LastHeardEntry` | a new voice command + result landed on the kitchen strip |
| `last_heard_undo` | `id` | a last-heard result was undone |
| `clarification` | `Clarification` | camera saw an unexpected plate/removal |
| `clarification_resolved` | `id` | a clarification was answered/dismissed |
| `order_submitted` | `Order` | a new order was sent to the kitchen |

---

## 5. Data shapes

```jsonc
// MenuItem
{ "id":"bulldozer", "name":"The Bulldozer", "price":16.0,
  "category":"Mains",                        // Appetizers | Mains | Desserts (menu sections)
  "station":"Grill", "prep_seconds":480,
  "desc":"Double smash burger, cheddar, crispy onions, pickles, house sauce." }

// Order
{ "id":"ord-t12", "table":12, "server_id":"srv-1",
  "delivery_mode":"all_together",            // or "as_ready"
  "status":"partially_ready", "elapsed_s":500,
  "dishes":[ /* Dish */ ] }

// Dish
{ "id":"d12-1", "k":1, "name":"Burger", "seat":1,
  "modifiers":"No onion", "allergy":"Peanut allergy",
  "station":"Grill", "zone":"12·1",
  "status":"ready",        // queued | cooking | ready | picked_up | served
  "est_min":null,
  "source":"camera",       // camera | tapped | null  (how it was marked ready)
  "note":"" }

// HeardOrder  (head-chef callout, not yet line-confirmed)
{ "id":"heard-t7", "raw":"Order table 7", "table":7,
  "items":["Burger","Chicken bowl"], "delivery_mode":"all_together" }

// Ingredient  (camera-tracked counts)
{ "name":"Patties", "expected":5, "seen":4, "stock":18 }

// Clarification  (camera needs a human answer)
{ "id":"clar-…", "zone":"9·2", "kind":"placed", "text":"Plate seen in Zone 9·2, which dish?" }

// LastHeardEntry  (kitchen strip)
{ "id":"lh-…", "cmd":"starting 12·2", "result":"Zone 12·2 cooking",
  "dishId":"d12-2", "prevStatus":"queued" }   // dishId/prevStatus power Undo
```

**Zone** is the per-dish kitchen slot, formatted `"<table>·<index>"` (e.g. `12·2`).

---

## 6. Wiring the real backend

There are two realistic paths. Pick based on what the backend exposes.

### Path A — a REST/WS order API matches `api.*`
If a service implements the routes in §3 (`/menu`, `/orders`, `/dishes/{id}`,
`/ingredients`, `/heard/{id}/confirm`) returning the §5 shapes, just set
`USE_REAL_API = true` and point `config.js` at it. Add a WebSocket that calls the
event-bus `_emit` (or `api._bus.*`) for live updates. **No endpoint for `/menu` et al.
exists today** — this is net-new backend work.

### Path B — adapt the existing voice backend (recommended)
The backend in `backend/app/server.py` is **not** an order API — it is a voice
mismatch-detection pipeline:

| Backend | Shape |
|---------|-------|
| `POST /session/start` | `→ { session_id, max_seconds }` (optional Basic auth) |
| `POST /session/{id}/kill` | `→ { killed: true }` |
| `GET /scenarios` | `→ [{ name, description }]` |
| `WS /ws/{session_id}` | **send** `{type:'transcript',text,speaker_turn}` or `{type:'scenario',name}` or binary mic audio or `{type:'mic_stop'}`; **receive** one message per parsed call: |

```jsonc
// WS result message from the backend
{ "raw_text":"four salmon for seat one", "item":"Salmon", "quantity":4,
  "station":"Grill", "speaker_turn":"chef", "is_call":true,
  "matched":true, "reason":null, "ticket_id":"t-123" }
```

Write a small adapter (e.g. `backend-adapter.js`, loaded after `data.js`) that opens
the session + socket and translates each result into bus calls:

```js
// sketch — maps backend WS results onto the UI event bus
const { session_id } = await fetch(`${API_BASE}/session/start`, {method:'POST'}).then(r=>r.json());
const ws = new WebSocket(`${API_BASE.replace('http','ws')}/ws/${session_id}`);
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (!m.is_call) return;                           // background chatter — ignore
  bus.voiceHeard(m.raw_text, { name: m.item, qty: m.quantity });  // transcript + pending item
  if (m.matched === false) {                        // mismatch vs ticket queue
    bus.plateUnexpected(/* zone derived from m.ticket_id/station */);
  }
};
```

Backend vocabulary → UI concept:

| Backend term | UI concept |
|--------------|-----------|
| `raw_text` | `voice_transcript.text` / `LastHeardEntry.cmd` |
| `item` + `quantity` | `voice_item { name, qty }` |
| `is_call: false` | background chatter — drop it |
| `matched: false` + `reason` | a `clarification` (dashed-blue "needs confirm") |
| `ticket_id` | map to an `Order`/`Dish` + its `zone` |
| `/scenarios` + `{type:'scenario'}` | test-fallback that drives the same bus path |

The adapter is the whole integration: screens and `bus.*` stay untouched, and the
test-scenario path exercises the identical code (same guarantee the backend makes in
`ARCHITECTURE.md §2.2`).

---

## 7. Gaps / notes for the integrator

- No order-CRUD backend exists yet; `api.*` read methods will fall back to mock until
  Path A or B is built.
- `server_id`/table/seat/zone are UI constructs — the voice backend has no notion of
  them. An adapter must assign a dish/zone to each `ticket_id`.
- `config.js` is the only place the backend URL belongs. CORS is already wide-open on
  the backend for the demo.
- Live mic needs `DEEPGRAM_API_KEY` set on the backend (see `backend/.env.example`);
  the UI never holds that key.
