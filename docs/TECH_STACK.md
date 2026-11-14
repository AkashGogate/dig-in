# Stack and integration status

FastAPI/Python 3.11+, Pydantic, uv lock, pytest/Ruff and buildless static HTML/CSS/JS are retained. SQLite/SQLAlchemy supports the old call-log experiment; **MVP v2 state/outbox is in memory**, not that SQLite database. No frontend framework, new platform install or paid dependency is required.

| Component | Current seam / limit |
| --- | --- |
| Menu | Canonical Pydantic/JSON schema, deterministic alias/modifier matcher; importer protocol/status only |
| Voice | Constrained ephemeral text parsing and visible hold/release transcript simulator; no live capture/STT/noisy-hall claim |
| CV | Stable-duration/no-hand/status/versioned occupancy command seam and mock controls; no pixel detector or verified UNO Q ingestion |
| Core | One-process locked v2 state, revisions, all-K zone allocation, timestamps/notifications and canonical events |
| Analytics | Background fake/JSONL export, retry outbox, local analyzer, ten-order fixture and Databricks SQL templates; live warehouse/dashboard adapter unimplemented |
| Screens | Server/Kitchen static web app, API polling, explicit manual fallback; not a native app/offline transaction system |
| Legacy | Frozen broad v1 coordination/tasks, original parser/WebSocket/audio/eval; isolated state and older semantics |

`uv sync --locked --python 3.11` installs the normal baseline. Heavy Pipecat/Daily/Silero pipeline remains optional via `--extra live-pipeline`; retained direct Deepgram legacy paths require a provider key only when actually used. Live adapters must verify current official APIs/capabilities before integration; previous names or a supplied brief do not establish working connections.

Current configuration is in [.env.example](../.env.example) and `frontend/config.js`. Databricks Free Edition/warehouse limits/Zerobus availability, actual CV throughput/two feeds, live speech privacy/latency and deployment remain unverified. POS/payments/spoken responses/positioning are deferred. Target Qualcomm relevance comes from the user’s plan, not verified prize rules.
