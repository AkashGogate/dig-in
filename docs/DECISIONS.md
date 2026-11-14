# Decisions and supersession ledger

Current decision date: 2026-11-14. Product intent is [PROJECT_SPEC](../PROJECT_SPEC.md); implementation evidence is [STATUS](STATUS.md). This ledger records current choices, not every brainstorming proposal.

| Decision | Current meaning / superseded behavior |
| --- | --- |
| Menu owns Core/backend and integration | Confirmed role assignment; personal names remain unassigned. Supersedes the brief’s unowned core concern |
| Four workstreams, two primary screens | Voice, CV, Menu/Core, Databricks; default Server/Kitchen only. Voice→Server and CV→Kitchen zones are proposed UI splits, not assigned people |
| Voice can create the draft | Deliberate read-back produces menu-constrained editable entries; manual baseline retained. Supersedes earlier supplement-only capture; no voice submission |
| Exact match first, vector similarity second | Spoken orders and chef callouts parse into structured fields (table, dish, quantity, modifiers) that must match menu aliases and tickets exactly; embeddings blur numbers/negation ("two" vs "three", "no pickles" vs "extra pickles", table 4 vs 14). A deterministic character-trigram cosine layer (`voice.suggest_items`) only ranks review candidates for misheard dish names on `unknown_item` flags; it never selects. Ranking ambiguous chef-callout→ticket clarification candidates the same way is a future Core option, still tap-confirmed |
| Table mismatch/unknowns block send | Explicit review/resolution, current revision and human Confirm tap required. Diarization is not identity |
| One dish unit per zone | Reserve all K free zones on acknowledgment or wait with none. Quantity two has two zones. Supersedes arrival-time batch bays/courses |
| Camera readiness is in MVP | Ready-only convention; stable no-hand occupancy/removal, default1500ms. Supersedes v1 staff-ready default/optional single-plate auto-ready flag |
| Unknown is not empty | Blocked/offline/uncertain feeds never free zones. Unexpected/returned plates and stale assignments require safe rejection/review; tap recovery retained |
| All-ready notification | Current task adopts one notification after every required dish ready, partial count before it. Pickup and optional delivered remain distinct |
| Timers, not percentages | Actual per-dish start and known typical minutes; missing fields stay unknown |
| Ingredients second priority | Countable observed/reviewed movement scaffold; no recipe double deduction or progress from hands |
| Databricks a fourth lane | Analyze service waits and voice/camera failures through canonical events, batch outbox and simulated data. Never live operational authority |
| No raw capture analytics | Preserve structured facts/counts, source identity/time and simulation/outcome labels; no audio/transcripts/video |
| Explicit breaking version v2 | New lanes use `/api/v2`; frozen `/api/v1`/legacy UI isolated, no automatic migration/dual-write |
| Deferred | Positioning, tasks/helpers/priority, POS/payments, courses, spoken responses; retained code does not put them back into MVP |
| Kitchen-only views | No dining-room camera, faces/guest tracking or raw video retention |

Still provisional: individual owner names, proposed screen split, real kitchen mic/hold-to-talk details, 60-second escalation, workspace edition/warehouse/quota/Zerobus and actual hardware/noise performance. No live speech/CV/cloud integration or remote push/publication is implied. The original brief’s Free Edition claims are unverified inputs, not implemented guarantees.
