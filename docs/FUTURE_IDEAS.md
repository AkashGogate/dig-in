# FUTURE_IDEAS.md

Brainstormed, not scoped, NOT implemented. Logged so the idea isn't lost — nothing here exists in code.

## Live kitchen-roll-call → online menu sync
Core idea: when the kitchen fires/86's an item (captured by the existing call-parser/mismatch pipeline), push that change out to a real-time online menu so it's visible outside the kitchen, not just logged internally.

Rough directions worth exploring later:
- **86-board sync**: when an item runs out mid-service (an "86 the duck" call), reflect that live on an online ordering page / QR-code menu, so customers don't order something that's already gone.
- **Prep/pace signal**: expose a lightweight "items fired in the last N minutes" feed — could inform a host stand or a waitlist app about kitchen pace, not just raw calls.
- **Front-of-house heads-up**: a non-blocking notification to servers when a fired item doesn't match what's on a customer's ticket (the existing mismatch detector), closing the loop between kitchen and floor instead of just logging it.
- **Multi-kitchen/location rollup**: if this ever runs across more than one kitchen, an aggregated "what's running low across locations" view.

## Open questions to resolve before scoping any of this
- Is the "online menu" a real target system (Square, Toast, a custom site) or would this need to build one from scratch? Changes the whole scope.
- Real-time push mechanism — webhook out from the FastAPI backend, or does the menu system poll?
- Does this stay back-of-house-only (PROJECT_SPEC.md's current non-goal boundary around front-of-house/customer-facing features), or does it deliberately cross that line? Worth deciding explicitly rather than drifting into it.

## Async kitchen-to-server comms / "heard" paging system
Core idea: a second, two-way channel distinct from fire-call capture. Servers get kitchen state (queue position, backed-up orders, item-ready pages) asynchronously - via a mic at a station they walk up to and trigger themselves, or an earpiece/phone feed - and pull messages on their own downtime rather than being interrupted mid-table. Includes a lightweight "heard" acknowledgment so a page is marked handled without needing a full reply.

Deliberately asynchronous by design: the explicit goal is to NOT erode the social/table-side interaction servers are mid-task on. This is the opposite direction of the current pipeline (kitchen voice -> structured log); this would be kitchen state -> server, pulled on demand.

Open questions before this gets scoped:
- This is kitchen-to-FLOOR-STAFF comms, not customer ordering, so it doesn't trip the "no customer-facing ordering" non-goal literally - but it's a second, much larger product (two-way dispatch/paging) layered on top of the current one (one-directional call capture). Worth deciding explicitly whether this becomes v2 of kitchen-copilot or a separate project, rather than drifting into it.
- Where does the "heard" ack get stored/surfaced - same structured log as fire calls, or a separate message queue entity?
- Earpiece/phone delivery implies a whole notification-delivery mechanism (push, SMS, a companion app) that doesn't exist anywhere in the current scaffold.

## Why this is a note, not a build
PROJECT_SPEC.md's whole discipline is "ship one scoped thing end-to-end, resist scope creep." This is exactly the kind of idea that's worth capturing before it's forgotten, but wrong to start building before the current scope (noise-robustness, Coval/eval, live-mic verification) is actually finished and demoable.
