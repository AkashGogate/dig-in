# Dig In — restaurant coordination MVP

Two screens, one shared backend: a server reviews an order, the kitchen acknowledges and starts each dish, and one assigned ready-only plating zone represents each physical plate. The runnable baseline uses **FastAPI/Python 3.11+, uv and static HTML/CSS/JavaScript**, with menu-driven simulations plus opt-in Deepgram and CV adapters. The default local mode requires no paid credentials or hardware.

Start at [AGENTS](AGENTS.md) and [docs/INDEX](docs/INDEX.md). [PROJECT_SPEC](PROJECT_SPEC.md) is current scope; [STATUS](docs/STATUS.md) separates implemented, simulated, adapter-only and future work. The **Menu workstream also owns Core/backend and integration**; personal owner names still need assignment. [WORKSTREAMS](docs/WORKSTREAMS.md) maps the four lanes to real files.

## Run locally

```bash
cd backend
uv sync --locked --python 3.11
uv run uvicorn app.server:app --host 0.0.0.0 --port 8000 --no-access-log
```

In another terminal from the repository root:

```bash
python3 -m http.server 5173 --directory frontend
```

Open [Server/Kitchen MVP](http://localhost:5173), [API docs](http://localhost:8000/docs), [menu](http://localhost:8000/api/v2/menu), or [generated contracts](http://localhost:8000/api/v2/contracts). Select a simulated staff/device session. Use two server tabs and a kitchen tab against **the same one-worker backend**. Restart/reload loses orders, sessions, deduplication receipts and pending analytics rows. Backend outage is visibly unsynced; offline transactions are not promised.

`frontend/config.js` uses localhost port8000 locally and same-origin `/api` behind Vercel. Configure a reachable backend explicitly when serving on a phone/LAN. A phone’s `localhost` is the phone itself. `.env.example` documents modes; uvicorn does not automatically read the root example. Export variables or deliberately run with `--env-file ../.env` after copying the example. Do not put secrets in browser code. The optional old Pipecat pipeline requires `uv sync --locked --extra live-pipeline`; it is not needed for this MVP.

To demonstrate menu independence, restart with a different reviewed JSON menu:

```bash
cd backend
DIG_IN_MENU_PATH=fixtures/menus/second.json uv run uvicorn app.server:app --port 8000
```

Unknown kitchen fields in that second menu remain null. [Mutable menu pipeline](docs/MENU_PIPELINE.md) supports JSON/CSV/item-per-line input, automatic vectors, reviewed runtime activation, and pinned ticket revisions. **Menu setup** lets a demo lead upload/paste, automatically encode, review and activate a menu in the app. `scripts.menu_tool` also prepares canonical JSON plus vectors offline; `fixtures/menus/dig-in.json` matches the existing eight-dish artwork. Default vectors are lexical hashing; an opt-in semantic API adapter is implemented with mocked tests, not live validation. PDF/PNG/JPEG extraction and editable correction are implemented through [local OCR](docs/MENU_EXTRACTION.md). See the [agent task map](docs/AGENT_TASK_MAP.md) and [teammate integration guide](docs/INTEGRATION_GUIDE.md). Hold/release defaults to a labeled **text-transcription simulator**; deliberately configured Deepgram enables transient PCM microphone streaming through the same reviewed draft path. The CV lane now has an opt-in producer into canonical versioned zones; screen controls remain labeled simulations. See [deployment](docs/DEPLOYMENT.md) and [CV integration](cv-service/V2_INTEGRATION.md) for modes, auth, evidence and real-device limits.

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
| `backend/app/mvp/` | Current v2 order/zone/menu authority, bounded voice relay and CV bridge |
| `cv-service/`, `schema/` | Actual producer, owning event schema and opt-in v2 sampler/worker |
| `kitchen-backend/` | Preserved standalone CV backend; isolated legacy regression target |
| `Dockerfile`, `fly.toml`, `frontend/vercel.json` | Root API image, one-worker Fly deployment, authenticated Vercel proxy |
| `backend/app/analytics/`, `analytics/` | Canonical events, retry outbox, local analyzer/export and Databricks SQL templates |
| `backend/fixtures/menus/`, `backend/fixtures/analytics/` | Portable menus and labeled simulated examples |
| `frontend/` | Default Server/Kitchen MVP; preserved v1 coordination and original voice lab |
| `backend/app/coordination/` | Frozen broader v1 demo with isolated state, tasks/helpers/old ready convention |
| `backend/app/`, `backend/eval/`, `audio-samples/` | Preserved parser/mismatch/legacy audio harness and regressions |
| `docs/` | Product/architecture, API/migration, four workstreams, Git workflow, decisions/status/runbooks |

`/api/v2` is authoritative for new work. `/api/v1` and [coordination-v1.html](http://localhost:5173/coordination-v1.html) remain a separate legacy demo; [legacy.html](http://localhost:5173/legacy.html) retains the original voice lab. Orders do not synchronize between versions. See [API](docs/API.md) for explicit migration semantics.

Local commits/docs are not automatically on other computers. Use separate clones/task branches and [the documented Git handoff](docs/DEVELOPMENT.md). The reviewed integration branch is `codex/application-integration`; source publication does not update production automatically. The hourly local heartbeat compares remote hashes and reviews changed refs; unchanged refs trigger no builds or paid calls.


Server and Kitchen now have a documented [service coordination extension](docs/SERVICE_COORDINATION.md):
canonical dish lineup, targeted kitchen-to-server updates and requested role-specific
summaries, with explicit device Print and optional Speak/Stop. Menu setup continues
to supply shared menu revisions. [Agent task map](docs/AGENT_TASK_MAP.md) and
[integration guide](docs/INTEGRATION_GUIDE.md) identify extension seams and reviews.

Production URL, login secret names, release checks and current live gaps are documented in [DEPLOYMENT](docs/DEPLOYMENT.md) and [STATUS](docs/STATUS.md). Keep keys in ignored local `.env` or platform secret stores, never in chat or Markdown.

The incoming UI screens are now connected: `server-order.html`,
`server-tables.html` and `kitchen.html` use canonical /api/v2 through data.js.
Navigate from the workbench or between operator pages. Sessions are selected per
page; saved orders remain on the backend. Original prototypes remain unloaded
reference. See [UI contracts](frontend/INTEGRATION.md) and the latest STATUS for
real-provider results, reviewed uncertainties and deployment gaps.
