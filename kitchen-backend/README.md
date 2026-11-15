# kitchen-backend

> This standalone teammate implementation is preserved with its regression tests. The integrated application uses canonical backend/app/mvp/Restaurant and the [v2 CV bridge](../cv-service/V2_INTEGRATION.md); this service is not started or dual-written by the active app.


Single source of truth for tickets, bays, running tasks and inventory, driven by CV
observations (`BACKEND_SPEC.md`). FastAPI + SQLite, one process. Kept separate from the
voice backend in `../backend` so its Fly deployment is unaffected.

## Run

```bash
uv sync
uv run python -m kbackend.app --port 8002          # reads ./config.yaml (or $KITCHEN_CONFIG)
uv run pytest
```

Full loop without cameras (two terminals):

```bash
cd kitchen-backend && uv run python -m kbackend.app --port 8002
cd cv-service && uv run python -m cvsvc.main --mock --backend-url http://localhost:8002/cv/events
curl -XPOST localhost:8002/tickets -H 'content-type: application/json' \
     -d '{"table":"12","course":"main","plates_expected":2,"dishes":["burger"]}'
curl localhost:8002/state
```

The ticket gets bay A, CV shows the label, two mock plates arrive -> ticket `ready` and a
running task appears; claim it (`POST /tasks/RUN-1/claim {"server_id":"s1"}`) and the mock
empties the bay -> ticket `served` (source `cv`), bay cleared, label reset.

## Config (`config.yaml`)

| Key | Default | Meaning |
|---|---|---|
| `cv_base_url` | `http://localhost:8001` | CV service, for context pushes and zone resolves |
| `event_source` | `http` | `http`: CV POSTs to `/cv/events`; `ws`: backend subscribes to CV `/events` |
| `readiness_mode` | `auto` | `auto`: full bay -> ready. `confirm`: arrival is "plated (observed)", a cook declares ready |
| `auto_serve_on_removal` | `true` | unclaimed removal in auto mode -> served + badge + review item |
| `cv_stale_after_s` | `10` | heartbeat gap before a camera is marked `lost` and its values `stale` |
| `allocate_on` | `submit` | or `cooking_complete` (`POST /tickets/{id}/cooking-complete`) |
| `bays`, `zones`, `recipes` | | bay ids; zone seed stock; dish -> [{zone, qty}] |

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/cv/events` | one event or an array; schema-validated, deduped on `event_id` |
| WS | `/ws` | sends `{"kind":"state"}` first, then `{"kind": ticket|bay|task|zone|review|camera|active_ticket|cv_event, ...}` |
| GET | `/state` | tickets, bays (with `plate_count_stale`), queue, tasks, zones (with `observed_count_stale`), cameras, review items, `cv_link` |
| POST | `/tickets` | `{table, course, plates_expected, dishes, seats, vip}` (called by the order flow) |
| POST | `/tickets/{id}/status` | `{status: kitchen_ack|preparing}` |
| POST | `/tickets/{id}/ready` | cook declares ready (confirm mode, or manual fallback) |
| POST | `/tickets/{id}/served` | server confirms served; overrides a camera-derived served |
| POST | `/tickets/{id}/cancel` | releases reservations, task and (empty) bay |
| GET | `/tasks` | running-task queue: oldest ready first, then VIP |
| POST | `/tasks/{id}/claim` / `release` / `complete` / `block` | duplicate claim -> 409 with `claimed_by` |
| PUT/DELETE | `/active-ticket` | `{ticket_id, set_by}`; forwarded to CV |
| GET | `/review-items` | open items |
| POST | `/review-items/{id}/resolve` | `{resolution: accept|reject|correct, count?, ticket_id?, staff_id?}` |
| POST | `/inventory/{zone}/restock` / `waste` / `correct` | `{qty}` / `{qty}` / `{count}`; CV baseline is re-synced |
| POST | `/bays/{id}/override` | `{action: clear|reassign, ticket_id?, confirm: true}` (logged) |
| GET | `/event-log`, `/observations` | audit trail; every entry has `source` (`cv`/`staff`/`system`) and time |

## Rules worth knowing

- **Context to CV** (`cvlink.py`): bays, claims and active ticket are pushed as full replaces
  after the commit, retried with backoff; a failed push never rolls back state. All three are
  re-pushed when CV restarts (its `/health` `boot_id` changes) or comes back after a gap.
- **Bays**: free = no ticket, last plate count 0, no unresolved pickup. No free bay -> FIFO
  `waiting_for_bay`. A bay is cleared only by a removal that empties it, a staff served/review
  resolution once CV reports it empty, or a confirmed override.
- **Ready (auto)**: plate count reaches `plates_expected`. This assumes cooks only put complete,
  ready-to-run plates in a bay; it is an operating convention, not proof the camera understood
  the meal (say so in the pitch). Extra plates or plates in an unassigned bay -> review item.
- **Served**: an emptying removal with a claim -> served (source `cv`). Unclaimed -> served with a
  "served, unclaimed pickup" badge plus a review item (auto mode), otherwise review only and the
  bay is held. Plates reappearing after served are logged as a return; the ticket is not reopened.
- **Inventory**: reservations reduce `available`, never `on_hand`; an attributed pick lowers
  `on_hand` and the ticket's reservation in one transaction. Pending changes and snapshot
  mismatches become review items and never overwrite `on_hand` on their own.
- **Camera health**: events from a camera CV reports as obstructed/lost are stored but not acted
  on. A heartbeat gap marks the camera `lost` and its values stale. Manual ready/served always work.
- **Outbox bursts**: batches are processed in `observed_at` order; older bay/zone/camera readings
  never overwrite newer ones, and ticket states only move forward (staff can override).
