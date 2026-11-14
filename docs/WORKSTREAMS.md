# Four workstreams and integration ownership

**Confirmed role decision: the Menu workstream owner also owns Core/backend and integration.** No individual names were supplied; each personal owner slot below is unassigned until the team names someone. This is not a fifth unowned core lane. Suggested screen splits are recommendations awaiting agreement.

| Lane / owner slot | Own paths and deliverables | Depends on / next concrete handoff |
| --- | --- | --- |
| Voice — person unassigned | `backend/app/mvp/voice.py`, voice tests; proposed `frontend` Server capture/review modules | Consume Menu IDs/aliases and v2 commands. Hand off deliberate provider adapter, constrained kitchen phrases/ambiguity and no-transcript retention; preserve manual/Confirm gates |
| Computer vision — person unassigned | `backend/app/mvp/vision.py`, new device/CV adapters, zone-specific tests; proposed Kitchen zone panel paths agreed before edits | Consume core zone assignments/versions and ingredient map. Hand off stable occupancy/no-hand/status/unexpected cases; validate UNO Q/geometry/feed, never directly mutate state |
| Menu **+ Core/backend/integration** — person unassigned | `backend/app/mvp/menu.py`, `contracts.py`, `domain.py`, `fixtures.py`, `api.py`; menus; root setup/CI/shared shell and integration docs | Menu contract owner, operational contract owner and integration-owner role. Review dependent changes; keep allocation/idempotency/flag gates authoritative; sequence entry-point/schema merges |
| Databricks — person unassigned | `backend/app/analytics/`, `backend/fixtures/analytics/`, `analytics/`, analytics tests | Consume canonical events unchanged. Hand off local batch/retry/analyzer/SQL; choose workspace and verify official live APIs before claiming a connector/dashboard |

`backend/app/analytics/events.py` is the **single event schema**, with Core responsible for accepted emission/identity/time semantics and the Databricks lane maintaining export consumption. Shape/vocabulary changes require Menu/Core + Databricks review and Voice/CV review when they supply metadata. `menu.py` is the single menu schema; new lanes do not hardcode fixture dish names. `contracts.py` owns state/commands and requires dependent consumer review.

## Suggested screen split and shared files

Voice→Server; CV→Kitchen zone panel; Menu/Core→kitchen queue/timers, shell and shared client integration is a practical proposed split. The team must explicitly accept it and claim component files before parallel edits. `frontend/app.js` initially holds both screens, so two agents must not edit it simultaneously; first agree an extraction/task boundary or sequence through Menu/Core. Backend `domain.py`, shared fixtures, schemas, `server.py`, root setup and STATUS also require coordinated claims. Existing lane modules and fixture directories give independent work against stable examples; a proposed future folder is not an implemented service.

## Handoff protocol

Use one unique task handoff with base commit/branch, owner role, claimed paths, consumed/emitted schemas, fixtures, checks, gaps and next action. Agree ownership outside the file before editing; a handoff/STATUS file is not a lock. Small scoped commits/PRs flow through Menu/Core integration; no force-push/main overwrite, no overwriting others’ uncommitted work. See [DEVELOPMENT](DEVELOPMENT.md) for precise Git transfer and shared runtime setup.

Immediate human decisions: name the four people (Menu’s person also carries Core/integration), accept/refine the proposed screen split, choose physical camera/board and analytics workspace. Cloud/hardware choices do not block credential-free mock lanes.
