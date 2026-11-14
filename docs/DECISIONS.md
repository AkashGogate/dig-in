# Decision ledger

Current product decisions supplied 2026-11-14. Full invariants live in [PROJECT_SPEC](../PROJECT_SPEC.md); this ledger explains the consequential choices without asserting implementation.

| Decision | Reason / consequence |
| --- | --- |
| Expand the earlier kitchen-only voice experiment into Dig In coordination | Preserve the working parser/evaluation harness; supersede its “no manual substitute” and no-front-of-house restrictions. Manual role screens are now required. |
| Structured phone draft is the order record; read-back speech proposes a reviewed diff | Speech never silently overwrites or submits. Human tap confirms the current table+food revision; payment is separate. |
| Optional positioning only on Start order; table then freezes | Prevent casual proximity from creating/reassigning orders. Hardware geometry and staff association are unverified; always keep manual selection. |
| Reject dining-room monitoring; use exactly two conceptual kitchen views | Ingredient zones and physical plating bays only. No facial recognition/guest tracking; event processing/no raw recording by default. |
| Keep observation evidence distinct from commands | A hand/withdrawal cannot establish quantity, ownership, readiness, or completion. Staff may correct; preserve provenance/unresolved uncertainty. |
| Keep acknowledgment, preparation, partial plating, ready, pickup, served distinct | Cook voice or tap is sufficient. Aggregate dish units rather than first-ready plate. Staff explicitly confirms served. |
| Assign bays at order arrival, queue when full | Current requested rule. Allocating near plating is a later recommendation to reduce bottlenecks, not an adopted silent change. Batch/course identity and stale assignment protection matter. |
| Default readiness is cook command | Optional auto-ready requires explicit convention/flag and initial single-plate restriction; no claim that vision verifies food/modifiers/doneness. |
| Separate recipe expectations, raw observations, accepted movements and stock | Prevent double deduction. Support return/restock/waste/correction and unresolved attribution. |
| Shared authoritative backend and atomic/idempotent transitions | Independent browser localStorage cannot coordinate staff. Single-process in-memory demo is acceptable; production durability/auth is future work. |
| Explain task priority; N helpers means N additional people | Ready food/wait time dominate, aging limits starvation, VIP secondary; no hidden LLM/emotion rank or worker surveillance. |
| Keep stack and paid/hardware seams small | Existing FastAPI/uv/static HTML remain. Deepgram/ElevenLabs optional; UNO Q feasibility unverified; Databricks optional analytics; no live POS/payments. |
| Target Qualcomm prize; rules unverified | Do not present user-described categories as audited eligibility or promise board throughput. No deployment/push authorized by scaffold work. |

Historical deployment, Coval, and stack claims are archived in [legacy context](archive/2026-11-14-legacy-context.md). Current status must come from checked source and recorded checks.
