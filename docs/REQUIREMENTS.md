# MVP requirements map

[PROJECT_SPEC](../PROJECT_SPEC.md) owns intent; [STATUS](STATUS.md) owns actual implementation. The normalized [team brief](MVP_TEAM_BRIEF.md) and [decision ledger](DECISIONS.md) explain narrowed scope.

| Requirement | Executable boundary / evidence |
| --- | --- |
| Human-reviewed table/menu draft; unknown/mismatch blocked | `app/mvp/contracts.py`, `menu.py`, `voice.py`, `domain.py`; menu/voice and MVP domain tests |
| One physical dish per zone; all K reserved on ack | MVP domain allocation, zone versions, capacity/retry tests |
| Stable no-hand ready-only occupancy/removal and tap recovery | Zone observation/status/reconciliation actions; mock evidence, not live CV |
| Partial progress then one all-ready notification; timers | Per-dish timestamps and aggregate notifications; no percent cooked |
| Menu independent, alias/modifier IDs, null kitchen details | Canonical menu schema, starter/second JSON and matcher/import-status tests |
| No double stock deduction | Separate recipe expectation/observation/accepted movement; ingredient scaffold second priority |
| Nonblocking analytics, identity/time/outcome and retry dedup | CanonicalEvent, outbox, fake/JSONL adapters; failure tests and labeled ten-order fixture |
| Four lanes with owned core integration responsibility | Menu owner also owns Core/integration; names and proposed screen split pending |
| Two primary screens and portable context | Server/Kitchen v2 default; Git docs/handoffs; isolated legacy demos |

Deferred: positioning, shared queue/helpers/priority, courses, spoken responses, POS/payments. Production auth/durability/cloud/hardware and noisy-hall performance require later evidence. No dining-room camera or raw capture analytics.
