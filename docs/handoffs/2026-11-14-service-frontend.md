# Service-flow frontend: separate operating views and on-demand summaries

- Owner/claim: requested frontend lane under Astra Max supervision. Isolated clone
  `codex/service-flow-frontend` over the existing uncommitted Menu/Core baseline.
- Paths: frontend/service-coordination.js, tests/service-coordination.test.cjs,
  app.js, index.html, mvp.css, frontend/AGENTS.md, CI workflow, this unique handoff.
  No backend/shared source docs edited, and no staging/commit/push/publication.
- Implementation: Server retains ordering first, followed by a scoped Kitchen
  update inbox and explicit service summary request. Kitchen gains a canonical
  dish-unit cooking lineup, ticket-targeted structured update composer/sent feed,
  and its own scoped summary. Messages and their seen/handled status never change
  food milestones. Dynamic lineup includes seat, modifier snapshots, guest request,
  known/unknown timing, table and exact unit/ticket IDs. Start remains possible
  after acknowledgment while zones wait; Ready requires a zone without review.
- Contracts: consumes state.service_updates and GET /api/v2/service/summary with
  audience=server|kitchen, demo session header. Writes publish_service_update,
  acknowledge_service_update and resolve_service_update through shared dispatch;
  canonical start_dish/ready_dish also use that exact-retry path. Backend owns
  identity, recipient scope, revision guards and every accepted transition.
- Summary output: text is always displayed; explicit browser Print, Speak and Stop
  are capability-detected presentation options. No automatic speech on request,
  update or polling. Speech stops on actor/view/state/offline changes; stale
  summaries cannot print/speak; delayed responses from another session/view are
  discarded. Session changes clear the summary and printable data. Browser voice
  output does not guarantee headphone routing or remote-voice privacy properties.
- Checks: JavaScript syntax and HTML unique-ID/label inspection passed. Twelve
  focused service behavior cases run in native Node VM with assertions cover
  explicit speech, stale/state/session/view cancellation, permissions/offline/
  uncertain writes, escaped notes, printing fallback, canonical unit details,
  start-while-zone-waiting, zone review, focused-button restoration and unchanged-state elapsed timer refresh. CI is wired
  for Node test runner; remote CI was not run. Root performs combined backend and
  browser verification; physical print/audio/headphones/screen reader are not
  established by these VM checks.
- Supervisor review: Astra identified missing unit distinctions, start/zone mismatch
  and polling focus loss. All were corrected with regressions. Final combined
  review and runtime checks remain the integrator's responsibility.
- Sources checked: MDN speech synthesis [speak](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/speak),
  [cancel](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/cancel),
  and browser [print](https://developer.mozilla.org/en-US/docs/Web/API/Window/print).
- Integration: deferred legacy general task/helper/priority system remains isolated;
  frontend AGENTS explicitly permits this new bounded canonical lineup/update/
  summary extension. Preserve existing menu upload/extraction and user edits.
