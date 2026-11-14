# Dig In — restaurant coordination MVP

Two screens, one shared backend: a server reviews an order, the kitchen acknowledges and starts each dish, and one assigned ready-only plating zone represents each physical plate. The runnable baseline uses **FastAPI/Python 3.11+, uv and static HTML/CSS/JavaScript**, with menu-driven transcript and camera simulations. No paid credentials or hardware are required.

Start at [AGENTS](AGENTS.md) and [docs/INDEX](docs/INDEX.md). [PROJECT_SPEC](PROJECT_SPEC.md) is current scope; [STATUS](docs/STATUS.md) separates implemented, simulated, adapter-only and future work. The **Menu workstream also owns Core/backend and integration**; personal owner names still need assignment. [WORKSTREAMS](docs/WORKSTREAMS.md) maps the four lanes to real files.

## Run locally

```bash
cd backend
uv sync --locked --python 3.11
uv run uvicorn app.server:app --host 0.0.0.0 --port 8000
```

In another terminal from the repository root:

```bash
python3 -m http.server 5173 --directory frontend
```

Open [Server/Kitchen MVP](http://localhost:5173), [API docs](http://localhost:8000/docs), [menu](http://localhost:8000/api/v2/menu), or [generated contracts](http://localhost:8000/api/v2/contracts). Select a simulated staff/device session. Use two server tabs and a kitchen tab against **the same one-worker backend**. Restart/reload loses orders, sessions, deduplication receipts and pending analytics rows. Backend outage is visibly unsynced; offline transactions are not promised.

`frontend/config.js` defaults to the serving host on port 8000; configure its base URL for a shared host. A phone’s `localhost` is the phone itself. `.env.example` documents modes; uvicorn does not automatically read the root example. Export variables or deliberately run with `--env-file ../.env` after copying the example. Do not put secrets in browser code. The optional old Pipecat pipeline requires `uv sync --locked --extra live-pipeline`; it is not needed for this MVP.

To demonstrate menu independence, restart with a different reviewed JSON menu:

```bash
cd backend
DIG_IN_MENU_PATH=fixtures/menus/second.json uv run uvicorn app.server:app --port 8000
```

Unknown kitchen fields in that second menu remain null. PDF/photo/model import is an interface/status stub, not a live importer. Hold/release on the server screen is an explicitly labeled **text-transcription simulator**, not verified microphone/STT. Camera controls simulate stable occupancy/removal, not image inference.

## Check and demo

```bash
cd backend
uv run pytest -q
# Against a fresh running backend:
uv run python -m scripts.mvp_smoke --base-url http://127.0.0.1:8000
uv run ruff check app/mvp app/analytics app/coordination scripts tests/test_mvp_*.py tests/test_coordination.py
uv run ruff format --check app/mvp app/analytics app/coordination scripts tests/test_mvp_*.py tests/test_coordination.py
uv run python -m app.analytics.analyze fixtures/analytics/ten_scripted_orders.jsonl --summary
```

Follow the [six-beat demo and failure probes](docs/DEMO_PLAN.md). [Analytics lane](analytics/README.md) includes a **SIMULATED** ten-order/20-dish dataset, retry export, SQL timeline/dashboard templates and metric definitions. Background fake export is the default; JSONL/disabled modes need no Databricks credentials. A live workspace/dashboard/warehouse remains untested.

## Map and compatibility

| Path | Purpose |
| --- | --- |
| `backend/app/mvp/` | Current v2 order/zone authority, menu/voice seams, fixtures, contracts/API |
| `backend/app/analytics/`, `analytics/` | Canonical events, retry outbox, local analyzer/export and Databricks SQL templates |
| `backend/fixtures/menus/`, `backend/fixtures/analytics/` | Portable menus and labeled simulated examples |
| `frontend/` | Default Server/Kitchen MVP; preserved v1 coordination and original voice lab |
| `backend/app/coordination/` | Frozen broader v1 demo with isolated state, tasks/helpers/old ready convention |
| `backend/app/`, `backend/eval/`, `audio-samples/` | Preserved parser/mismatch/legacy audio harness and regressions |
| `docs/` | Product/architecture, API/migration, four workstreams, Git workflow, decisions/status/runbooks |

`/api/v2` is authoritative for new work. `/api/v1` and [coordination-v1.html](http://localhost:5173/coordination-v1.html) remain a separate legacy demo; [legacy.html](http://localhost:5173/legacy.html) retains the original voice lab. Orders do not synchronize between versions. See [API](docs/API.md) for explicit migration semantics.

Local commits/docs are not automatically on other computers. Use separate clones/task branches and [the documented Git handoff](docs/DEVELOPMENT.md). No remote push/publication or live payment is part of this checkpoint.
