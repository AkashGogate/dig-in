# Workstream ownership slots

Assign names in the team's actual coordination channel. One slot may cover multiple lanes; no team size is assumed. Claims cover paths for a task, not permanent ownership of a product idea.

| Role slot | Primary paths | Interface/review dependency | Next useful task |
| --- | --- | --- | --- |
| Integration owner | root instructions, CI, releases, shared docs | All lanes; sequences shared-file changes | Review branch, run baseline, coordinate integration; no deployment assumed |
| Domain/contracts | `backend/app/coordination/contracts.py`, `domain.py`, `rules.py`, fixtures, domain tests | All consumers review breaking changes | Persist authoritative state/transactions; amendment and correction workflows |
| Server/role UI | `frontend/` | API contract owner, kitchen/shift workflow users | Refine phone ordering and correction review; responsive/manual fallbacks |
| Voice | new adapter modules under `backend/app/coordination/`, retained `deepgram_live.py`, `pipeline.py`, eval/audio tests | Session identity + proposal/command boundaries | Deliberate read-back capture, partial-diff clarification, unavailable fallback |
| Qualcomm hardware/vision | `backend/app/coordination/kitchen.py`, new device adapters/tests | Observation schema; inventory/bay transitions | Validate UNO Q ingestion and two-view feasibility, stable change events, obstruction state |
| Task coordination | `backend/app/coordination/tasks.py`, task-specific tests, agreed UI component paths | Atomic claims/helper model and domain owner | Group wait/split UX, targeted clarification, ranking evidence |
| Optional analytics | new `analytics/` or adapter module after agreement | Versioned exported events, no critical-path writes | Optional Databricks aggregates and demo metrics |
| QA/demo | `backend/tests/`, demo runbook, task-specific handoffs | Fixture/contract changes reviewed | Two-session smoke, stale observations, timing and prompt-burden measurements |

The transaction/order/bay/inventory orchestration is in `domain.py`; kitchen observations/dish rules are in `kitchen.py`, and task claims/helpers are in `tasks.py`. Pure rule functions require the caller’s transaction lock: invoke through `Restaurant.execute`, never expose them as a second authority. Coordinate shared contract and cross-domain changes. Likewise, the static role UI may initially occupy shared files, so partition work by component/module or sequence edits. Do not call a proposed folder an implemented service.

Shared files (`contracts.py`, fixtures, root setup, STATUS) require coordinated review. Use per-task handoff files and small commits, never a single shared status document as a pseudo-lock. Read [DEVELOPMENT](DEVELOPMENT.md) for Git/code sync versus runtime backend state.
