# Integration acceptance map

This maps the requested integration/scaffold to executable seams. STATUS records
actual tests and limits; DEPLOYMENT_HANDOFF records the release assigned to the
other signed-in agent. It does not claim that deferred production/hardware work
has been completed.

| Requested behavior | Integrated implementation | Verification / remaining boundary |
| --- | --- | --- |
| Load a new arbitrary menu in the app | Menu setup JSON/CSV/text plus PDF/PNG/JPEG extraction and editable proposals | Runtime/extraction/client tests; grouping remains reviewable, OCR is not perfect |
| Automatically encode, review, activate | menu_import/menu_embeddings, lead prepare/review/versioned activate | Atomic activation/provider-failure/stale checks; local vectors work offline; optional semantic provider has mocked transport only |
| Mutable menu without dish-specific parser edits | Canonical menu IDs/aliases/modifiers, menu snapshots and indexes | Second-menu regressions; old drafts/tickets retain their menu |
| Server ordering flow | Workbench and Take orders/My tables against v2 Core | Save/current revision/human Confirm, flags, exact retries and real browser tests |
| Kitchen cooking flow | Canonical physical dish lineup and Kitchen operator | Ack/start/ready/pickup separated; quantity2 has two actual zones, all-or-none/FIFO |
| Kitchen→front staff coordination | Structured owner-targeted updates and explicit role summaries | Separate ServerOne/Two tests, current actionability and message handling without food mutation |
| Device display, optional print/spoken summary | Workbench service-coordination module | Explicit/cancelable/stale-safe behavior tested; physical printer/headphone routing unverified |
| Real speech software and safe fallback | Bounded Deepgram PCM relay, pinned device ticket, menu parser and conservative confidence | Actual short v2 stream plus102 synthetic provider cases; real staff/room/mic/phone remains unverified |
| Actual teammate CV module | Owning producer schema, v2 sidecar/bridge/watchdog, counting/circles/reconnect | Synthetic frames/video/process and Core tests; actual six-zone calibration/hand model/rig remains necessary |
| Shared backend integration | One Restaurant authority, v2 contracts, event identity/outcomes and outbox | Full ASGI/HTTP/source/container CI; memory-only one-machine demo, no durable production guarantee |
| Analytics integration seam | Canonical background export, fake/JSONL adapter, simulated fixtures, SQL/analyzer | Local retry/dedup/analysis tested; no authenticated live Databricks warehouse |
| Teammate code preservation | Merge ancestry and unloaded UI prototypes; isolated standalone kitchen service | No fake UI fallback or second writer; original camera captures removed from current tip/ignored locally |
| Agent navigation and maintainability | AGENTS, INDEX, AGENT_TASK_MAP, lane contracts and unique handoffs | Clear entrypoints and dependent tests; arbitrary future snippets still require review |
| Submission hygiene | Ignore/Docker policies, hygiene CI, history/staged secret scans | Actual backend/.env remains ignored and undisplayed; no env/key committed |
| Fly/Vercel login and routing software | Global HTTP Basic gate, Node static gate, API rewrite, direct ticketed WS, root image/config | Linux/Vercel builds passed; actual production release and hosted verification delegated |
| Cheap future integration watch | Local hourly heartbeat plus remote-head comparison script | No work/build/provider calls when unchanged; machine/app availability required |

Default local demo uses manual controls and clearly labeled transcript/camera
simulations against a real shared backend. It must not silently fall back to
prototype records on outage. New operator pages link the full workbench for menu
setup, microphone capture, reconciliation and device output. Both remain usable.

Deferred scope remains positioning, generic helper/priority task engines, courses,
POS/payments and general conversational speech. Nothing here recognizes faces,
food identity/modifiers/doneness, or guests. Accepted stock is separate from recipe
expectations; a hand trip cannot deduct inventory or infer cooking progress.
