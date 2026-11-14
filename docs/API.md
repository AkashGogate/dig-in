# Coordination API and event contract

Source of truth: [`contracts.py`](../backend/app/coordination/contracts.py), [`domain.py`](../backend/app/coordination/domain.py), [`fixtures.py`](../backend/app/coordination/fixtures.py). Runtime schemas: [contracts](http://localhost:8000/api/v1/contracts), [OpenAPI](http://localhost:8000/openapi.json), [interactive API](http://localhost:8000/docs). Use your actual shared backend host in place of localhost. Frontend/voice/vision consumers must not independently redefine these shapes.

## Surface

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/sessions` | Select a fixture actor and obtain a simulated staff session; not production login |
| `GET /api/v1/state` | Shared snapshot, derived views, and adapter availability |
| `POST /api/v1/commands` | Validated command/observation envelope; domain owns transitions and deduplication |
| `GET /api/v1/contracts` | Schema version and generated JSON Schemas for commands/state |

`POST /sessions` accepts `{ "actor_id": "server-1" }` and returns `session_id` plus `actor`. Send that token as the `X-Demo-Session` header on commands. A successful command returns `{result, state, replayed}`; a domain conflict is HTTP 409 and schema validation is HTTP 422. `GET /state?section=window` (or the same `section` query on `POST /commands` for its response snapshot) filters the available-task ranking before selecting its top three. State snapshots include a `computed` view for balances, recipe expectations, ticket aggregates, ranked tasks and blockers. `Snapshot`, `SessionResponse`, and `CommandResponse` validate the API responses, and `/contracts` exports the full Snapshot schema. The retained `/session/start`, `/scenarios`, and `/ws/{session_id}` serve the original audio-call experiment and use a separate session/queue. They are not the coordination order API.

## Version 1 envelope

`Command` forbids extra fields and contains stable `id`, literal `schema_version: 1`, source, `kind` (command/observation), occurrence time, optional device/correlation identifiers, and an action-discriminated payload. Source values are manual, voice, mock_camera, camera, or positioning. Actor comes from the staff session rather than an untrusted speaker label. For a retry, preserve the entire original serialized envelope, including `occurred_at`, payload, source/device/correlation fields and stable ID. Do not regenerate a timestamp or rely on its default on retry: the same ID with changed content conflicts. Different operations require new IDs. Idempotency is scoped to the lifetime of this in-memory backend.

Example draft-start envelope (with `X-Demo-Session`):

```json
{
  "id": "demo-server-1-start-001",
  "schema_version": 1,
  "source": "manual",
  "kind": "command",
  "occurred_at": "2026-11-14T18:00:00Z",
  "device_id": "demo-phone-1",
  "correlation_id": "demo-run-001",
  "payload": {"action": "start_order", "table_id": "1", "use_positioning": false}
}
```

Only `confirm_send` with manual source and explicit current-revision human confirmation submits. A source field is protocol provenance, not proof a human acted: the browser approval UX and eventual production auth/trust boundary remain essential. Speech is allowed to propose/cook-command within authorized semantics; it cannot bypass order approval.

## Actions and identifiers

| Domain | Actions / safeguards |
| --- | --- |
| Draft/read-back | `start_order`, `edit_draft`, `readback`, `accept_correction`, `confirm_send`; revision/proposal IDs prevent stale approvals |
| Kitchen | `acknowledge`, `select_prep`, `advance_dish`; active prep context is recorded per cook, distinct from acknowledgment/stages; staff correction reason where required |
| Amendment | `amend`, `ack_amendment`; acknowledged changes are separate from original submission |
| Bays | `assign_bay`, `reconcile_bay`, `release_bay`; physical bay ID + expected assignment version, ticket/course/dish batch mapping |
| Evidence | `observe`; ingredient change, plate arrival/removal/return, obstruction; envelope kind is observation |
| Inventory | `accept_movement`; consume, return, restock, waste, correction, reason, optional observation and order attribution |
| Tasks | `create_task`, `task_action`; claim/release/join/leave/helpers/split/block/cancel/complete/urgent; additional helper count is explicit |

Table IDs identify physical tables; order IDs distinguish additions/tickets at that table. Line IDs identify configured order lines and seat/course; dish IDs distinguish individual units. Bay ID is physical location; assignment version guards late events after reassignment. Never match two salmon dishes solely by menu name or table number. Raw observations retain source/time/device and unresolved disposition until reviewed; accepted inventory movements are separate records with provenance. `select_prep` records active cook context, but observation `order_id` attribution remains explicit and optional; the mock does not infer it. `reconcile_bay` requires manual cook/lead review, current assignment version, observed occupancy and a reason. It can clear pickup ambiguity while food remains; clearing occupancy requires every assigned dish already picked up/served through its validated claimed-run path. Recipe reservations are expected usage, not an extra stock deduction.

The deterministic `MockReadback` supports one explicit quantity phrase such as `seat 1 salmon quantity 2`. Compound/ambiguous speech asks for clarification; missing items can be added manually. This is not a live transcript/NLU integration. Mock positioning suggests table 1 with an explicit review label; it is not measured range/triangulation. Fixtures configure three tables, two menu dishes sharing greens, countable zones, three capacity-two bays, two server actors, cook, and lead.

## Compatibility policy

Schema version 1 covers current executable shapes. Optional compatible additions may retain v1. Breaking field/meaning changes require a new version or explicit migration with dependent-lane review, fixture/consumer updates, and regression tests. Preserve stable IDs in replay fixtures. Check expected revisions and assignment versions at the domain boundary, not just in UI controls. Do not introduce a second schema in adapter payloads. See [DEVELOPMENT](DEVELOPMENT.md) for review and handoff requirements.
