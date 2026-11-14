# Agent task map — start here after bootstrap

Read root AGENTS → INDEX → PROJECT_SPEC → STATUS → WORKSTREAMS. Inspect Git status,
branch/worktree and scoped AGENTS first. Current task code can be uncommitted:
never reset, overwrite or assume a clean checkpoint. Source, not prose, owns shape.

| Need to change | Owning implementation | Consumer / focused check |
| --- | --- | --- |
| Server/Kitchen journey ownership and invariants | docs/SERVICE_COORDINATION.md | role-specific scenarios and integration review |
| Structured staff updates and summary shapes | mvp/service_contracts.py | service_flow.py; service endpoint/client tests |
| Canonical dish lineup and role-scoped summaries | mvp/service_flow.py | Restaurant transaction/read seam; test_mvp_service*.py |
| Device summary, inbox, Kitchen lineup, Print/Speak/Stop | frontend/service-coordination.js | shared app.js context/dispatch; service-coordination.test.cjs |
| PDF/photo decoding, OCR lines | mvp/menu_extraction.py; adapters/menu_ocr.swift | menu-document.js; test_mvp_menu_extraction.py |
| Dish grouping / provisional imports | menu_extraction.propose_items; menu_import.py | Menu setup correction; extraction/runtime tests |
| Canonical menu fields, aliases/modifiers | mvp/menu.py | Voice, setup, snapshots; menu_voice/runtime tests |
| Vector provider / similarity suggestions | mvp/menu_embeddings.py | menu prepare/search; runtime failure tests |
| Upload and extracted-item correction | frontend/menu-document.js | menu-setup.js; browser correction flow |
| Preview, review gates, stale/error/retry UI | frontend/menu-setup.js | app.js callbacks; tests/menu-setup.test.cjs |
| Shared request/session/exact command retry | frontend/app.js | all screens; browser outage/session flow |
| Menu prepare, snapshot pinning, activation | mvp/domain.py | API/client/analytics; runtime + core tests |
| Commands/state/operational schemas | mvp/contracts.py | Voice/CV/client; /api/v2/contracts; core tests |
| API ingress/status/HTTP errors | mvp/api.py | all adapters; route tests + real HTTP smoke |
| Voice transcription/parsing | mvp/voice.py; future speech adapters | Server/kitchen intents; menu_voice + core tests |
| Camera observations | mvp/vision.py; device adapters | versioned Core commands; core tests |
| Event identity/outcome/source time | analytics/events.py, domain emission | outbox/Databricks; analytics + core tests |
| Cloud export/query/dashboard | analytics/, backend/app/analytics/ | canonical events only; analytics tests |
| Run/configuration/CI | README, .env.example, Dockerfile, test.yml | locked tests + HTTP smoke |

Paths in the table are relative to backend/app unless marked frontend/docs/root.
Do not edit app/coordination or the old voice lab to implement v2 features. Those
are isolated legacy surfaces. Do not duplicate schemas in adapters/screens.

## State machines worth preserving

Document → provisional editable records → validated/encoded candidate → human
review → version-checked activation. Only new drafts use the activated revision.

Voice → editable draft with unresolved flags → current-revision human Confirm.
Menu matching and embeddings supply candidates, never authorization.

Order submitted → acknowledged/all-K zones or FIFO waiting → per-unit started →
ready → pickup/release → optional delivered. Acknowledgment is not a start time.

Accepted state/events/local enqueue happen together under Core's lock. OCR,
encoding and cloud sink I/O stay outside it. Rejected evidence is not a milestone.

## Change recipe

1. Find the row above, read its contract/scoped AGENTS, and claim exact paths with
   Menu/Core. Make a task branch/clone from the agreed checkpoint.
2. Implement at the seam; preserve manual fallback, unknown values, provenance,
   review gates and exact retry identities. Do not add new schemas casually.
3. Test a normal path and the failure the change can introduce. Use a second menu
   to detect hardcoded names. Shared contract changes also run core regressions.
4. Update STATUS with observed checks and limits; add a unique handoff. Link new
   architecture/configuration changes from INDEX. Never imply mocked/live parity.
5. Give Menu/Core the scoped diff/base/dependencies and reviewers needed. See
   [integration guide](INTEGRATION_GUIDE.md). No automatic commit/push/deployment.
