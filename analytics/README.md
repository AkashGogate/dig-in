# Analytics workstream: service gaps and sensor failures

This lane is implemented locally with a canonical event model, retry outbox, fake and JSONL adapters, ten **SIMULATED** scripted orders, a portable analyzer, and Databricks SQL templates. There is **no live Databricks connection/dashboard/workspace verification**. No cloud credentials or heavy SDK are required. Free Edition, SQL warehouse availability/quotas, live batch API semantics, and Zerobus eligibility remain unverified workspace decisions. No assumption from the supplied brief establishes availability.

## Run without credentials

From `backend/` after the normal locked setup:

```bash
uv run python -m app.analytics.analyze fixtures/analytics/ten_scripted_orders.jsonl --summary
uv run python -m app.analytics.export fixtures/analytics/ten_scripted_orders.jsonl --simulate-failures 1 --attempts 3
# Optional local file; ignored outputs directory, one writer process:
uv run python -m app.analytics.export fixtures/analytics/ten_scripted_orders.jsonl --jsonl-output outputs/events.jsonl
uv run pytest -q tests/test_mvp_analytics.py
```

`app/analytics/events.py` is the canonical v2 export contract, shared by core. Its stable event ID and original timezone-aware `time` survive export. `received_at` is a separate core receipt timestamp; it must never replace source time. `run_id`, `simulated`, and `outcome` distinguish scripted runs and accepted state facts from observed evidence. Dotted event types are extensible with shared-contract review, including aggregate `order.picked_up`. The complete MVP vocabulary lives alongside the model. Extra `zones.retry_requested`, `voice.clarification`, and `stock.observation` are observed outcomes, not accepted operational milestones. Core also exports reviewed draft counts/flag codes rather than capture content. Accepted `stock.changed` requires an accepted inventory movement; a raw change remains `stock.observation`. Rejecting a stale signal does not create an accepted dish transition. Nested raw transcript/audio/video fields are rejected; exported payloads must contain only reviewed structured facts and metadata. Actor identifies the session/device, never a recognized speaker.

## Outbox and ingestion boundary

Core calls `Outbox.enqueue(events)` locally after validated transitions. Enqueue never contacts analytics. A background worker/explicit exporter calls `drain(adapter, batch_size=100)` separately. A slow/failing adapter releases the queue lock during I/O, so operational enqueue continues. Failure preserves exact pending rows, attempt counts, and error health; retries retain event identity. Fake sink and JSONL sink deduplicate by event ID. Changed content under an existing ID fails. Core must atomically coordinate the local state commit and enqueue; a production implementation requires a durable transactional outbox.

The demo outbox, receipts and fake sink are **in memory**. Restart loses pending rows/receipts; a local JSONL sink preserves already exported rows but is not a production outbox, crash transaction, or cross-process database. CLI retries are within that process; after exit, retry from the same input file. Failed rows are never marked sent. Health exposes pending/sent counts, per-pending attempts, last error and `durable:false`. No external network send belongs in order/dish request handlers.

`BatchAdapter` and `SQLWarehouseAdapter` are interfaces, not working cloud connectors. Future adapter owner must verify current official workspace/API capabilities, implement parameterized batch ingestion, handle async statement/polling/quotas, and deduplicate rows by `event_id` before claiming live support. Backend pushes out; notebooks do not need access to the live restaurant backend.

`01_events.sql` defines the Delta table/staging MERGE shape; `02_timelines.sql` derives orders and physical dish units; `03_dashboard.sql` contains tile queries. They are **untested Databricks SQL templates**. Replace catalog/schema, validate parsing against the real workspace, stage batches, reject conflicting event versions, and designate one ingestion writer. Delta does not enforce event-ID uniqueness; an unchecked concurrent MERGE is not proof of deduplication. No secrets should be placed in tracked SQL or browser code.

## Metric definitions

- Stage durations use original source timestamps for submitted→acknowledged, acknowledged→first start, first start→all-ready, all-ready→all-picked-up, and per-dish ready→pickup. Aggregate ready/pickup facts come from core milestones, not a dashboard guessing from the first plate. Missing endpoints or invalid chronology produce null and explicit missing/censored counts; they never become zero. Optional delivery remains separately censored.
- Correction count in `order.submitted` is `corrected_draft_lines`: distinct IDs in the union of the initial voice draft and final submitted draft whose reviewed values differ: changed, added and removed lines. It counts changed lines, not edit taps. Report alongside `initial_voice_draft_line_count` and `capture_mode` (`manual`, `mock_voice`, `live_voice`). The initial voice line count is a denominator/context count; corrections can exceed it when new lines are added, so do not treat their ratio as bounded recognition accuracy. Manual-only drafts report zero voice corrections. Repeated edits to one line count once; reverted edits count zero. This is a pre-send review measure, not a noisy-speech accuracy score.
- Eligible automation actions are only `order.acknowledged`, `dish.started`, `dish.ready`, `dish.picked_up`. Mandatory Confirm and optional Delivered taps are excluded. `manual_action_share` is eligible tap actions/all eligible actions. `automation_available:false` plus `fallback_reason` supports confirmed unavailable-automation tap counts; their share uses actions with known availability as denominator. Null availability is reported separately as manual use, **not sensor failure**. Both denominator counts must be shown.
- Zone-wait durations apply only to orders with `zones.waiting`. Orders never waiting are counted separately, not assigned a fabricated zero. An unresolved wait remains censored until `zones.assigned`.
- Camera blocked/offline/unexpected tiles count events. They do not claim outage durations without device-specific recovery intervals. Inventory-versus-recipe is deliberately not computed while ingredient detection remains a reviewed scaffold; recipe expectation is not a stock deduction.

## Simulated fixture and sample results

`backend/fixtures/analytics/ten_scripted_orders.jsonl` has **106 events, 10 simulated orders and 20 physical dish units**, fixed source times/run ID, and per-event scenario labels. These are hand-scripted examples, not captured restaurant performance. Scenarios 4, 5 and 9 deliberately leave queued/ready/partial work incomplete.

| Question | Simulated count/result |
| --- | --- |
| Submit→acknowledge | 10 observed; median 10 seconds |
| First start→all-ready | 8 observed / 2 missing; median 149 seconds |
| Dish ready→pickup | 14 observed / 6 missing or censored; median 25 seconds |
| Voice draft corrections | 8 voice orders; 4 distinct corrected baseline lines / 16 baseline lines |
| Eligible tap actions | 14 / 59 actions; 7 known-unavailable, 7 unknown-availability taps |
| Known-unavailable tap share | 7 / 52 known-availability eligible actions |
| Zone waiting | 2 observed waits, median 30 seconds; 8 never-waiting orders |
| Camera evidence | 1 blocked status, 1 offline status, 1 unexpected-zone event |

The fixture intentionally makes some synthetic service gaps visible: time after the first start exceeds acknowledgment delay, two orders wait for zones, and tap use needs both availability and reason to distinguish manual use from degraded sensors. This is a demonstration of the analysis, not evidence that those are real bottlenecks. The local analyzer rejects mixed run IDs or mixed simulation labels; filter exports to one dataset before analysis. Every dashboard tile using it must show **SIMULATED** and run ID. A live rig/dashboard run within one minute remains untested.

## Ownership and handoff

Databricks owner slot is unassigned until the team chooses a person. This lane owns `backend/app/analytics/`, `backend/fixtures/analytics/`, `analytics/`, and its tests. The Menu role owns Core/backend/integration as the confirmed role decision, with the individual still to be named; it reviews changes to event types/identity/outcome/timestamps and owns operational emission; Voice/Menu/CV review metadata they supply. Suggested next task: choose a workspace/edition and owner, validate SQL and one optional batch adapter against official API docs, then run the same ten-script contract checks with failures/retries before integrating a live dashboard. No credentials or workspace activity is authorized by this scaffold.
