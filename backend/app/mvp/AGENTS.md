# MVP Core, Menu and Voice contracts

Read root AGENTS, PROJECT_SPEC, docs/API and docs/WORKSTREAMS. The Menu workstream owner also owns Core/backend integration; the person's name is TBD. Voice owns voice.py/adapters; CV produces versioned zone evidence, never allocates shared state independently. Agree path claims before editing domain.py, contracts.py, api.py or fixtures.py.

- `/api/v2` is the default MVP. `/api/v1` is a preserved, separate legacy demo; never mix their state or silently translate readiness semantics.
- Canonical MenuDocument lives in menu.py; canonical analytics Event lives in app/analytics/events.py; contracts.py imports both. No alternate schema copies in adapters/screens.
- Restaurant.execute owns the lock, revision checks, all-or-none FIFO zone allocation, state changes, canonical event emission and local outbox enqueue. Sink I/O never runs inside operational requests.
- Human Confirm tap is mandatory. Unknown/table flags require explicit review. Capture text is ephemeral and excluded from analytics; signed session/device identity is not diarization.
- Exactly one physical dish per zone. Stable no-hand occupancy means ready under the ready-only convention; stable removal/pickup releases the assignment. Unknown/blocked never means empty. Tap fallback must work without a start timestamp or camera. All-ready/picked-up facts emit once from every unit's milestones.
- New adapters must include event ID, source time, assignment version, run ID/simulation provenance and clear outcomes. A rejected/ignored observation is not an accepted transition.

Run the tests relevant to your lane plus tests/test_mvp_core.py for contract/transition changes. Preserve the original parser regressions. Update the lane handoff and status with actual checks; live hardware/cloud quality is not established by simulated tests.
