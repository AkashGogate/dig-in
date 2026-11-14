# Status — 2026-11-14 scaffold

Read [PROJECT_SPEC](../PROJECT_SPEC.md) for intended behavior. This file describes implementation, not an ownership lock or machine synchronization mechanism. Update capabilities only with source/check evidence; keep one task handoff per change.

## Capability boundaries

| Capability | State | Evidence / limitation |
| --- | --- | --- |
| Existing FastAPI/static HTML/uv repository | Implemented, retained | No framework migration; kitchen parser/mismatch/audio experiment preserved |
| Shared coordination contracts and fixtures | Implemented scaffold | `backend/app/coordination/contracts.py`, `fixtures.py`; schema v1, deterministic actors/tables/menu/zones/bays |
| Shared authoritative coordination state | Demo implementation | Single process/in-memory lock; reset on restart; no durable/multi-instance guarantee |
| Sessions/staff identity | Mock | Fixture actor session selection; not production authentication or diarization identity |
| Structured order and confirmation gate | Scaffold implementation | Current-revision human send; validate actual checks below |
| Read-back reconciliation | Mock, deliberately limited | Text input / one dish quantity grammar; targeted clarification, manual missing-item additions; no general NLU/live STT in role flow |
| Kitchen/bay/inventory/task transitions | Scaffold implementation | Versioned domain commands and observations; not production CV or stock sensing |
| Role screens | Local baseline | Server/kitchen/shift views against shared backend; no native mobile build |
| Positioning | Mock/disabled | Deterministic suggestion, manual path; no geometry/hardware validation |
| Ingredient/plating cameras | Mock observations | Exactly two conceptual kitchen views; no video inference/recording or contents/doneness verification |
| Automatic ready | Experimental, disabled by default | Only an explicitly configured complete-batch convention/single-plate experiment may enable it |
| Legacy call parser, mismatch, eval scorer | Implemented, retained | Separate seeded session queue and SQLite log; cannot submit structured Dig In orders |
| Deepgram / ElevenLabs | Legacy Deepgram code / candidate adapter | Live provider quality and integration unverified in scaffold; ElevenLabs not wired |
| Qualcomm UNO Q | Unverified work lane | No connected hardware or two-stream throughput claim |
| Databricks / POS / payments | Planned/optional / absent | Analytics off live critical path; no real cards or payment handling |
| Deployment | Outside scope | Existing deployment files/reports preserved; no push/publication performed |

## Current scaffold gaps

Read-back only proposes one quantity change; new-item detection/freeform transcription are not implemented. `select_prep` records active cook context, while ingredient attribution remains an explicit optional order ID rather than inferred camera ownership. Post-send amendments currently cover queued-line quantity changes, not arbitrary prepared-food edits. Raw observations do not prove stable CV detection. `reconcile_bay` supports manual cook/lead resolution of plate-return/pickup ambiguity using occupancy/version/reason; clearing food still requires a validated claimed pickup first. Task split currently records the staff decision/removes helper requirements rather than planning multi-plate routing. Fixture movements/tasks/observations are produced by scenarios/commands rather than preloaded operational truth.

## Verification record

Verified 2026-11-14 on macOS arm64, Python 3.11.18, locked default environment (Pipecat extra not installed):

- `uv sync --locked --python 3.11`: passed after making Pipecat optional and declaring SQLAlchemy asyncio support. The initial host had only Python 3.10/no uv; an isolated uv/Python environment was used. Pytest is pinned below 9 because the newly resolved pytest 9.2 runner crashed before test collection; the locked pytest 8.4.2 runner works.
- `uv run --locked --offline pytest -q`: **41 passed**, one dependency deprecation warning for Starlette’s httpx TestClient transport. Includes retained parser/evaluation tests and coordination API invariants, concurrent claims, bay uncertainty, conditional auto-ready count guards and ranking/aging.
- `ruff check app/coordination scripts tests/test_coordination.py`, `ruff format --check` on the same paths, and `python -m compileall -q app scripts`: passed. The formatter/linter is scoped to the new lane; legacy formatting was not rewritten. No separate static typechecker is configured; Pydantic input/output schema validation and integration tests check runtime contracts.
- `python -m scripts.smoke_demo --base-url http://127.0.0.1:8001` against a fresh full FastAPI server: passed. Two tables/tickets, read-back proposal/apply/human send, retry-safe send and stock, count removal/return, partial versus ready, claimed run/additional helper, pickup, explicit served, return/reconciliation/release. Assertions observed zero duplicate effects, wrong-ticket transitions, premature-ready at partial, and net stock error after return. Ready-to-pickup was ~0.006s **synthetic API timing**, not a human/hardware benchmark.
- Seven legacy mock eval clips executed via `asyncio.run(eval.run_eval.run('mock'))`: no missed/false calls in ground-truth transcript mode; checked-in scorecard preserved. This does not measure STT.
- Frontend `app.js` and `config.js`: syntax passed in Node VM through the available tool runtime; HTML IDs and label targets checked. CI also runs Node syntax checks; there is no frontend build step.
- Chrome browser: entered demo staff sessions; manual order with modifier/dietary request; quantity diff remained proposed until applied; human send; cook acknowledgment/select prep; mock arrival stayed partially plated; explicit ready; claim/pickup/served. The other unit remained queued. Inspected server at 390px and measured no document overflow at 320px; keyboard Tab reached a native control with a visible outline. Initial backend outage visibly showed UNSYNCED, then connected after startup. Shift view displayed stock expectations and mock/disconnected adapters. Inspected console slice showed extension warnings, no app errors. No screen-reader, physical-phone, full 200% zoom, cross-browser, live STT/CV, hardware, container build or deployment validation was performed.
- Documentation local links and `git diff --check`: passed. Original saved checkout contained only untracked `.DS_Store`; no omitted user scaffold was found. Historical deployment claims are archived and were not reverified.

Post-send amendment creation and detailed stage corrections are API-only; role UI asks for one additional helper while the API supports 0–6. Automatic ready has no public UI toggle and is off in fixtures; tests explicitly enable it. Multi-plate camera attribution asks for clarification when it cannot identify the staged/removed unit. Full group batching/routing and live voice interpretation remain future work. Backend sessions/state/receipts are deliberately transient and unauthenticated fixture identities, unsuitable for production or multiple workers.

## Next tasks by dependency

1. Review/merge the scaffold through the designated integration owner; assign owners to [WORKSTREAMS](WORKSTREAMS.md). Transfer tracked commits through Git; uncommitted worktree files are not on teammates' machines.
2. Persist state/idempotency with transactional claims and add real authentication before durable/public/multi-instance use.
3. Improve structured read-back proposal coverage and deliberate live capture without weakening human approval; validate noisy-room audio separately.
4. Validate UNO Q camera ingestion, stable portion changes, bay observation assignment versions, obstruction/degraded status, and optional constrained-ready operating convention.
5. Measure the reproducible demo metrics and refine wait/split/group-helper UI; treat unimplemented product details as open tasks, never implied capabilities.
