# Dig In

Restaurant coordination scaffold: structured server orders, kitchen stages and bays, inventory observations, and shared food-running tasks. The existing kitchen-call parser/mismatch/audio evaluation experiment is preserved. Current product intent is [PROJECT_SPEC](PROJECT_SPEC.md); begin as a contributor at [AGENTS](AGENTS.md) and [docs/INDEX](docs/INDEX.md).

The local demo uses FastAPI/Python, `uv`, and static HTML/CSS/JavaScript. No paid credentials, hardware, native mobile app, or Node build is required for the coordination mock. One backend process owns shared **in-memory** state; restart resets it. Demo sessions simulate signed-in staff and are not production authentication.

## Run locally

Requirements: Python 3.11+ and `uv`. The heavier Pipecat pipeline is optional (`uv sync --locked --extra live-pipeline`); the default install covers this server, tests and retained direct Deepgram WebSocket/eval code.

```bash
cd backend
uv sync --locked
uv run uvicorn app.server:app --host 0.0.0.0 --port 8000
```

In another terminal from repository root:

```bash
python3 -m http.server 5173 --directory frontend
```

Open [role app](http://localhost:5173), [API documentation](http://localhost:8000/docs), or the retained [kitchen-call experiment](http://localhost:5173/legacy.html). Use separate tabs/devices for two servers and a cook, all pointed at the same backend. Do not start multiple workers; do not use reload during a stateful demo. See [DEVELOPMENT](docs/DEVELOPMENT.md) for LAN URLs and cross-computer setup. The role app must display backend failures as unsynced; it does not queue approved offline orders.

Frontend API configuration is in `frontend/config.js`. `.env.example` explains optional settings and integration keys; none is required for coordination mocks. The original live-mic experiment needs a Deepgram key and has separate session/cost limits. Its microphone path is not the new structured-order submission authority.

## Check and demo

```bash
cd backend
uv run pytest -q
uv run ruff check app/coordination scripts tests/test_coordination.py
uv run ruff format --check app/coordination scripts tests/test_coordination.py
# With a fresh backend running (adds demo records):
uv run python -m scripts.smoke_demo
```

Follow [demo runbook](docs/DEMO_PLAN.md). [STATUS](docs/STATUS.md) records actual verification and limitations; [TESTING](docs/TESTING.md) distinguishes domain, API, browser, and real-audio checks. A mock transcript score is not a measurement of real speech recognition.

## Repository map

| Path | Purpose |
| --- | --- |
| `backend/app/coordination/` | Shared executable contracts, fixtures, domain transitions, API and mock adapters |
| `backend/app/` | Retained parser/mismatch/Deepgram experiment, SQLite log, FastAPI server |
| `frontend/` | Buildless role screens plus retained `legacy.html` experiment |
| `backend/tests/` | Domain/API invariants and existing parser/evaluation checks |
| `backend/eval/`, `audio-samples/` | Synthetic audio corpus and mock/real-STT evaluation harness |
| `docs/` | Architecture/API, decisions, workstreams, collaboration, status and runbooks |

## Collaborate

Assign role-based lanes from [WORKSTREAMS](docs/WORKSTREAMS.md), use one clone/worktree and branch per task, and review shared-contract changes with dependent lanes. Git transfers commits and docs; it does not synchronize uncommitted edits or running restaurant state. Share/integrate reviewed commits through your agreed remote workflow. No remote push, publication, payment, or live hardware capability is implied by this scaffold.
