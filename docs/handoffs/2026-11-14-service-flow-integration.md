# Separate Server/Kitchen flows and service handoff integration

- Owner / claim: Menu/Core integration, explicitly requested by user. Work delegated
  to isolated backend and frontend task clones; Astra at maximum reasoning supervises
  architecture and independently reviews both lanes and documentation. Root owns
  combined integration, evidence, bootstrap/task map and scope supersession.
- Base: c1d25fc plus the user's full prior uncommitted Menu/Core state, recorded by
  content hashes. Integration branch codex/service-flow-integration in isolated clone;
  backend/frontend branches are separate. No staging/commit/push/publication.
- Goal: record and implement distinct Server ordering/coordination and Kitchen
  cooking/lineup journeys, connected by structured order-linked updates and requested
  role-specific summaries displayed on devices with explicit Print/Speak/Stop.
- Scope decision: lineup projects canonical Dish units; there is no independent
  cooking task/priority engine and no revival of v1 state. Update acknowledgment/
  resolution is separate from food acknowledgment/start/readiness/pickup.
- Contracts: additive service_contracts + focused service_flow, existing Core
  transaction/receipts/outbox for writes; ephemeral single-snapshot summary reads;
  recipient/session-derived routing and revision guards; notes excluded from events.
  Existing global demo state snapshots are not a confidentiality boundary.
- UI integration: focused service-coordination module receives shared context/
  request/dispatch; existing menu import, human Confirm and service controls remain.
  Printing and speech are explicit optional presentation. Device audio routing is
  not guaranteed; no paid provider or always-on spoken assistant added.
- Preservation: both lane files are integrated by ownership lists, then only task
  deltas copied back after baseline-hash checks. Teammate snippets should use these
  seams with scoped handoffs and consumer review, never replace the scaffold.
- Review: Astra requested per-unit seat/modifier/request context, faithful start
  action projection while zone-waiting, and keyboard-focus preservation on polling.
  Implementing agents address these before combined acceptance checks.
- Final verification and limits: see current STATUS service coordination entry and
  lane handoffs for exact executed commands, counts, browser coverage and unverified
  printer/earpiece/live-provider behavior.


Final integration evidence: full135 backend tests, Ruff39 files and21 UI VM cases
passed; existing real HTTP MVP smoke passed. Real browser two-role handoff and
server-session recipient separation passed, including partial pickup/current-ready
vs cumulative-ready and explicit update ack/resolve. HTTP confirmed read-only
summaries and note-free canonical update events. Astra independently ran16 backend
and12 service UI cases and cleared final source. Browser audio/headphone routing,
physical printing, broad accessibility and remote CI were not executed.
