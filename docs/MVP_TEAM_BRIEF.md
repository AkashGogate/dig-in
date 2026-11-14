# Restaurant coordination MVP — normalized team brief

Normalized 2026-11-14 from the supplied design brief and the user’s follow-up decisions. This portable note replaces dependence on a private file/chat. [PROJECT_SPEC](../PROJECT_SPEC.md) owns current intent; [STATUS](STATUS.md) owns implementation evidence. Example dishes/cloud suggestions in the supplied brief are not verified integrations.

The demo spine is: choose table → manual or deliberate voice draft → human review/Confirm tap → kitchen acknowledgment → atomic one-zone-per-plate reservation → per-dish start/timer → stable ready-only zone occupancy → partial then all-ready notification → stable pickup/free → optional delivered. Camera coverage is kitchen only: plating first, countable ingredients second.

## Four workstreams and the missing-core concern

| Workstream | Builds / gives others | Responsibility decision |
| --- | --- | --- |
| Voice | Menu-constrained editable drafts; constrained acknowledge/start; visible capture and tap fallback | Role owner name unassigned; Server screen is suggested ownership |
| Computer vision | Occupancy/no-hand stability, status, unexpected/returned plate review; ingredient counts second | Role owner name unassigned; Kitchen zone panel is suggested ownership |
| Menu / Core | Canonical menu/matcher/import-review seam **and authoritative backend/event endpoint/integration** | User-confirmed combined responsibility; individual still to be named |
| Databricks | Event ingest/export, timelines, simulated evaluation and service/sensor gap analysis | Role owner name/workspace unassigned; never a live operational dependency |

The original brief left Core/screens unowned. The follow-up assigns Core/backend/integration to Menu’s owner. It does not assign names or confirm the proposed UI split. Shared contracts are reviewed across dependent lanes, with Menu/Core coordinating integration; [WORKSTREAMS](WORKSTREAMS.md) maps real paths and handoffs.

## Agreements carried forward

- Server selects table and deliberately reads it first. A menu-constrained draft is editable; unknowns/ambiguity flag candidates. Spoken-table disagreement blocks Confirm until explicit resolution. Voice never submits/authenticates. Audio is discarded after transcription; analytics contains structured facts/counts, not capture content.
- One physical dish unit gets one assigned zone. Quantity two needs two IDs/zones. Reserve all K on acknowledgment or wait with none; no partial allocation. Table is not an order identifier. Late camera events need the assignment version.
- Ready-only convention makes stable occupancy mean ready, without a second human-ready tap by default. Stability is 1–2 seconds and no hand; removal uses the same rule. Camera-offline/blocked/unknown is not empty. Unexpected/returned plates prompt review; taps recover operation.
- Acknowledged is not started. Show elapsed/typical time if known, never cooked percentage. Partial counts precede one all-ready notification; optional delivered is distinct from pickup.
- Menu JSON is first-class and replaceable. Aliases/modifier IDs drive every new consumer; imported station/call-out/time/recipe/mapping stay unknown until reviewed. The arbitrary PDF/photo importer is future adapter work.
- Ingredient changes need stable countable evidence/review; expected recipes and accepted movements do not both deduct. A hand is not consumption/progress.
- Events keep stable identity, actor/source/time and accepted-versus-observed meaning. Core validates before emitting facts. Backend batches export outside service requests; failure retries retain pending rows. Ten labeled simulated orders unblock dashboard work.

## Analytics questions

Measure stage waits, ready-food delay, distinct corrected voice-draft lines, eligible tap/fallback share, zone waiting, blocked/offline camera and unexpected-zone counts. Confirm taps are ordinary required approval, not fallback. Missing endpoints are null/censored. Sample counts and SIMULATED labels are mandatory. Ingredient-versus-recipe comparison remains conditional. See [metric definitions/data/SQL](../analytics/README.md).

## Deferred and provisional

Positioning, task/helper/priority queue, POS/Square/payments, courses and spoken responses are deferred. No dining-room camera or worker emotion/performance surveillance. Existing legacy experiments are separate from the MVP.

The supplied brief’s kitchen push-to-talk, 60-second food escalation, Free Edition/warehouse/quotas and Zerobus ideas are provisional. No workspace capability or live dashboard is established. Current instructions adopt all-ready notification and elapsed/typical timers; the other proposals require team/workspace validation. Hall-noise/headset quality, actual camera stability and UNO Q throughput are not verified by mock tests.

Build taps first, then replace adapters independently. Demo six beats: two-item reviewed order; acknowledge/reserve; start a dish; first stable plate shows partial count; block camera and tap-ready the second; pick up/free and inspect exported timeline. Record a backup video only when a real rig run is authorized; this scaffold does not claim one exists.
