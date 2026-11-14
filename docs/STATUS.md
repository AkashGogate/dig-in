# Status — MVP v2 checkpoint, 2026-11-14

[PROJECT_SPEC](../PROJECT_SPEC.md) owns intended behavior; this file owns execution evidence. [Normalized brief](MVP_TEAM_BRIEF.md) is portable team context. The Menu workstream **also owns Core/backend and integration**; personal names remain unassigned. STATUS is not a concurrency lock.

| Capability | Status / practical limit |
| --- | --- |
| FastAPI/Python/uv/static stack | Implemented, retained; no new platform/framework |
| Two primary Server/Kitchen screens, `/api/v2` | Implemented local demo; shared backend state, exact retry IDs; not native/offline transactions |
| Menu JSON/schema/store/matcher | Implemented deterministic aliases/modifier IDs, two menus; order name/kitchen-field snapshots; unknown imported fields remain null |
| Voice draft and kitchen grammar | Real parser/flags; optional live Deepgram nova-3 streaming (off unless `DIG_IN_VOICE_LIVE=1`), menu-alias keyterms, demo-password ticket, per-stream/daily/IP spend caps + `/api/v2/voice/usage`. Two approved live runs on a synthetic `say` clip only; no real mic/noisy-hall validation |
| Current-revision human send | Implemented; unknown/table mismatch explicitly resolved, voice cannot submit; correction counts defined in product/API |
| One-zone-per-physical-unit on ack | Implemented atomic all-K/FIFO retry/capacity/version rules; six simulated zones A–F |
| Ready-only occupancy/removal | Implemented event rules using simulated producer evidence (1500ms/no hand); no image detector or verified UNO Q feed |
| Camera blocked/offline/unexpected/tap recovery | Implemented demo status, unknown occupancy, review, tap-ready/pickup; no feed-health hardware proof |
| Per-dish start/timer, partial/all-ready/pickup/delivered | Implemented timestamps/progress and once-only all-ready notification; missing starts remain unknown; delivered optional |
| Ingredient tracking | Second-priority countable observation/review/movement scaffold, not real ingredient CV; expected recipe does not deduct |
| Canonical events/outbox/export | Implemented local contract, identity/time/outcome validation, background fake/JSONL retry/health; memory pending rows lost on restart |
| Databricks evaluation assets | 106 labeled SIMULATED events / ten orders /20 units, local analyzer and SQL/dashboard templates; no live dashboard/workspace tested |
| Live menu OCR/importer, CV/Databricks adapters | Adapter-only or future; no paid credentials needed. Live STT adapter exists (voice row) but is off by default |
| Legacy preservation | Frozen `/api/v1` broad coordination in coordination-v1.html and original legacy.html voice lab; isolated state/contracts, not MVP defaults |
| Deferred | Positioning, task/helper/priority queue, courses, spoken responses, POS/payments |
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
