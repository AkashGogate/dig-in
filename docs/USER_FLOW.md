# Two-screen MVP flow

Use [DEMO_PLAN](DEMO_PLAN.md) for scripted checks and [STATUS](STATUS.md) for what actually ran. All operational clients share one `/api/v2` backend. Demo sessions identify staff/devices honestly and do not authenticate recognized voices.

## Server

Choose table → Start order → manually add items or deliberately hold/release the **mock transcript** capture → editable menu-ID draft. Review quantities, modifiers/requests and optional seats. Unknown/candidate flags block send; edit then explicitly dismiss reviewed unknowns. A spoken-table mismatch requires keep-selected/use-spoken choice. Every revision is reviewed; human **Confirm and send** is the only submission. No audio is recording in the text simulator; future live capture must discard it after transcription.

Submitted orders show kitchen acknowledgment, ready count/total and pickup progress. Partial plates do not create an all-ready notification. One all-ready notification appears after all required units reach ready. Pickups can be camera evidence or explicit staff taps; optional Delivered follows all pickups. Outage remains visibly unsynced; retry the exact uncertain envelope, never assume local success.

## Kitchen

Acknowledge ticket by tap or constrained mock kitchen phrase. Core reserves K zones for K physical units, or waits FIFO with no partial allocation. Start a specific dish to run elapsed/known typical time. Repeated dishes or same-table additions ask for an order/unit selection rather than guessing. Zone labels show table, order/dish identity and assignment version.

Only finished plates enter ready-only zones. Stable no-hand occupied evidence marks the assigned unit ready; stable removal after occupancy picks it up/frees the zone. Block/offline status means unknown, not empty. Tap Ready/Pickup and reviewed reconciliation keep service usable. Unassigned occupancy/returned plate prompts review; stale/hand/unstable/empty-before-ready cannot silently complete food. Retrying zones is available when capacity recovers.

Menu details and camera/analytics state expose uncertainty. Ingredient review is secondary; expectation does not deduct stock. No shift/task/helper/positioning/course/payment/spoken-response navigation belongs in the MVP default. The separately linked legacy demos do not share v2 orders.
