# Dig In — current MVP specification

Decision date: 2026-11-14. This is the current agreed scope, normalized from the [supplied team brief](docs/MVP_TEAM_BRIEF.md) and later user decisions. [STATUS](docs/STATUS.md) describes actual capability. The earlier expansive scaffold is preserved as [v1 context](docs/archive/2026-11-14-v1-scaffold.md), not the default product.

## Product and responsibility

The MVP has **two primary service screens: Server and Kitchen**, using one authoritative shared backend, plus a secondary **Menu setup** screen for lead upload/review/activation. Four workstreams are Voice, Computer vision, **Menu/Core**, and Databricks. The user confirmed that the **Menu workstream owner also owns Core/backend and integration**; no individual names have been supplied. Proposed UI split: Voice develops the Server screen; CV develops the Kitchen zone panel; Menu/Core coordinates shared shell, kitchen queue and contract integration. That screen split is a proposal, not assigned people. See [WORKSTREAMS](docs/WORKSTREAMS.md).

## Reviewed orders and voice

A server selects a configured table and either enters menu items manually or deliberately holds/releases capture and reads back the order. A menu-constrained parser produces an editable draft using configured item/modifier IDs, quantities and optional seat/dietary requests. Unknown terms/ambiguous matches return flags and candidates, never invented items. The server says the table first; a spoken/selected table mismatch **blocks submission** until an explicit choice. Manual edits do not silently clear unresolved flags. Voice alone cannot submit: a human **Confirm and send** tap must approve the current revision. Sending never authorizes payment.

The menu owns item names, aliases, modifiers and optional kitchen fields. Orders snapshot item ID/name, station, typical time and recipe where known, so later menu edits cannot rename an open ticket. Missing imported kitchen details remain unknown/null. The MVP accepts structured JSON/CSV/item-per-line text through a prepare/review/activate pipeline, with automatic vector indexing and a deterministic matcher. PDF/PNG/JPEG input uses local OCR and heuristic grouping to create editable provisional dishes before encoding/review; accuracy on arbitrary layouts remains unverified. Local vectors are a lexical baseline; an opt-in semantic provider adapter is implemented but not live-validated. Runtime menu changes pin existing drafts/tickets to their original menu revision. Loading another menu must require no parser/domain code change. See [MENU_PIPELINE](docs/MENU_PIPELINE.md).

Demo sessions honestly simulate staff/device identity. Diarization/speaker labels are not authentication. Capture is deliberate; audio is discarded after transcription. V2 retains structured draft facts/counts rather than raw transcripts/audio, and exports no raw capture content. The old voice lab is isolated and retains its historical logging behavior; do not route MVP capture through it.

Correction count is reproducible: compare the most recent voice draft baseline against the confirmed final lines by stable line ID and menu ID/quantity/modifiers/seat/requests. Count distinct changed, added or removed line IDs once; repeated edits to one ID count once and a full revert counts zero. Export `corrected_draft_lines`, `initial_voice_draft_line_count`, `final_line_count` and `capture_mode`. A count including additions may exceed the baseline line count; it is not a speech-accuracy percentage. Pure manual drafts have no voice baseline.

## Kitchen and physical plating zones

The kernel is **submitted → kitchen acknowledged → per-dish started → ready → picked up → optional delivered**. Acknowledgment does not start cooking. Elapsed timers use actual start timestamps with menu typical minutes when known; missing starts/typical times remain unknown, never percent cooked. Voice or tap may acknowledge/start; ambiguous kitchen phrases must ask for a specific order/dish, especially repeated dishes or multiple orders for one table.

On acknowledgment reserve **K free physical zones atomically for K dish units**. Quantity two requires two distinct dish IDs/zones, not one zone per menu line. If capacity is insufficient, record `zones.waiting` with no partial allocation/overbooking. Retry FIFO as zones free and expose a manual retry path. Order/dish IDs identify the work; table number is display context. Each assignment has a version, rejecting stale camera events. The starter fixture has six zones A–F and a maximum six-unit order; larger requests need explicit splitting.

The default MVP uses the explicit convention **only finished plates enter assigned ready-only zones**. Stable occupancy for 1–2 seconds with no hand (configured demo default 1500ms) marks that physical dish ready. Stable removal after occupancy marks it picked up and frees its zone. This is occupancy detection plus an operating convention, not food identity, modifier or doneness recognition. Producer-reported stable evidence in the mock does not establish real CV accuracy.

Partial progress shows ready units out of total. Emit one `order.ready` notification when every required dish has reached ready; do not notify the whole order on its first plate. Pickup and optional delivered are separate. A plate picked up before the last dish is ready retains its ready milestone.

Unassigned occupancy produces `zone.unexpected` and a review prompt. Returned plates, unknown/blocked/offline feeds, hands, unstable samples, stale versions or empty-before-ready events must not silently free/reassign food. An unavailable feed is **unknown, not empty**. Staff have explicit tap Ready/Pickup and reconciliation controls, including blocked-camera fallback. Tap-ready may occur without a known start time; analytics keeps that duration missing. No extra staff-ready confirmation is required after valid default camera evidence.

There are exactly two conceptual kitchen camera views: plating zones first, fixed countable ingredient zones second. No dining-room video, faces/guest tracking or raw video retention. Board/camera processing and two-feed performance on Qualcomm UNO Q remain unverified.

## Ingredients and analytics

Ingredient detection is second priority: scaffold countable samples, uncertainty/review and accepted movements. A hand alone is not stock change/progress. Recipe expectation, raw observation and accepted movement/balance remain distinct; never deduct both recipe and observed consumption. Returns/restock/waste/corrections preserve provenance and reason. Unclear quantity/attribution stays unresolved.

Core emits canonical versioned events with stable `event_id`, order/dish targets, type, tap/voice/camera/system source, actor, source time and payload. [CanonicalEvent](backend/app/analytics/events.py) is the only new event contract, enriched with receipt time, run/simulation label and accepted-versus-observed outcome. Rejected/stale evidence is not an accepted milestone. Duplicate IDs must not repeat operational effects or export rows. Validated state and local outbox enqueue share the core transaction; adapters never mutate state directly.

Databricks analyzes **where service loses time and where voice/camera fail**. Backend export runs outside requests, batches events and preserves pending failures/retries/health. It must never make a live order wait for cloud analytics. Fake/JSONL modes and ten labeled simulated orders unblock development without cloud credentials; SQL warehouse ingestion is an adapter interface and SQL/dashboard templates remain untested in a real workspace.

Metrics use source timestamps for stage durations, per-dish ready-to-pickup, corrected draft lines, eligible manual fallback actions, zone waiting, camera blocked/offline and unexpected zones. Mandatory Confirm/optional Delivered taps do not count as automation fallback. Missing stages have null/censored counts, not fabricated zeros. Inventory-versus-recipe analysis is conditional on implemented ingredient evidence. Every simulated tile/result must say SIMULATED and include counts. See [analytics definitions](analytics/README.md).

## Server–Kitchen coordination and requested summaries

The 2026-11-14 follow-up authorizes a bounded service coordination scaffold:
separate Server ordering/coordination and Kitchen cooking/lineup journeys, structured
kitchen updates to the owning server, recipient handling, and on-demand deterministic
role-scoped summaries. Summaries display on device, with explicit Print and optional
Speak/Stop presentation. The kitchen lineup projects canonical dish units and never
creates a second cooking state machine. Update handling never changes food milestones.
See [SERVICE_COORDINATION](docs/SERVICE_COORDINATION.md) for both complete flows.

## Deferred and provisional

Deferred from default MVP: positioning, independent task/priority engine, helpers, priority scoring, courses and POS/Square/payment. The bounded canonical lineup/update/summary and explicit spoken-summary follow-up above supersedes the earlier blanket deferral of tasks and spoken responses; general conversational spoken responses remain deferred. Existing v1 code remains isolated to preserve previous work. Production auth/durability, live speech/CV/hardware and cloud deployment are not implied by the scaffold.

The supplied brief proposed kitchen push-to-talk, all-ready notify, 60-second escalation and Free Edition. Current task explicitly adopts one all-ready notification and elapsed/typical timers. Kitchen microphone behavior and 60-second escalation remain provisional; escalation is not required/implemented. Free Edition/SQL warehouse/quotas/Zerobus availability require workspace verification, not assumption. The team still needs individual names for the four role owners and confirmation of the proposed screen split; Menu/Core responsibility itself is settled.
