# 2026-11-14-service-backend: separate service projections and handoffs

- Owner role / coordination claim: Menu/Core backend integration subtask assigned
  by root; Astra supervisor reviewed architecture and canonical-lineup semantics.
- Branch / base commit: `codex/service-flow-backend`, isolated clone over
  `c1d25fc08e6cee5cdd74949211be38601f39f7c7` plus the previous uncommitted scaffold.
  Only the backend task paths listed below changed; no staging/commit/push.
- Claimed paths / dependencies: new `service_contracts.py`, `service_flow.py`,
  additive MVP contracts/domain/API hooks, analytics event vocabulary,
  `test_mvp_service.py` and this unique handoff. Frontend consumes the same schema.
- Goal / acceptance criteria: separate server/kitchen operational projections,
  typed kitchen→order-owner updates, explicit recipient handling, deterministic
  on-demand device summary, unchanged physical cooking and human approval gates.
- Implemented changes: canonical Dish/order lineup projections (no duplicate task
  state machine); tap-only kitchen publish plus recipient/lead acknowledge/resolve
  with expected revisions; stable exact-retry receipts/state/event/outbox commit.
  GET `/api/v2/service/summary?audience=server|kitchen` captures identity/state/time
  together and returns role-scoped orders, per-unit lineup, current pickup counts,
  open updates and deterministic text. Read causes no event/export mutation.
- Contract/schema compatibility and dependent reviewers: additive State
  `service_updates`, service commands and service event vocabulary. `/contracts`
  exposes summary schema. Unit context includes snapshotted item name, modifiers,
  seat, request, known timing and zone review state. Existing start/ready/pickup
  commands remain authority: an acknowledged queued dish can start without a zone,
  but readiness still requires assigned/non-review zone. Pickup updates derive
  current actionability, never count a historical picked-up unit as collectible.
- Checks actually run, results, date: 2026-11-14. 16 focused service cases passed;
  full suite 135 tests passed, with existing dependency deprecation warning.
  Scoped Ruff lint/format passed. Root performs combined frontend/HTTP/browser
  integration checks separately; no local speech/hardware/cloud validation here.
- Mocked/experimental/unverified behavior: one-worker in-memory demo state;
  summaries are deterministic projections, not an LLM/ETA predictor. Explicit
  authored notes persist in service state but are omitted from analytics payloads;
  raw capture fields are rejected and voice/camera cannot publish staff notes.
  No private-inbox claim: existing `/state` and command responses are global demo
  snapshots and expose authored notes. Summary scope and recipient command guards
  are tested, but production auth/confidential snapshots are separate work.
- Remaining task / blocker / next owner: root integrates scoped backend paths,
  frontend consumes summary/update contracts, shared reviewers validate the merged
  behavior. Browser speech/printing is presentation only and must be opt-in.
- Integration notes and potential conflicts: contracts.py/domain.py/api.py and
  analytics/events.py are shared files. Copy only task-owned versions against the
  agreed unchanged baseline; preserve prior uncommitted menu/OCR/voice/CV work.
