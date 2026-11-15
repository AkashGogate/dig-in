# Voice + menu/service application integration

- Branch/base: isolated `codex/voice-application-integration`, merging Voice
  `9af39dc` into reviewed menu/service `9d3face` with `--no-commit --no-ff` for
  conflict inspection only. Root performs the real ancestry merge and resolves
  deployment/auth/shared docs. This lane does not commit, push, deploy or spend.
- Preserved: canonical eight-dish IDs/descriptions/categories, snapshot modifier
  names and historical menu revisions; menu upload/OCR/correction/encoding and
  local suggestion provider; Server/Kitchen service modules/events/outbox and
  human current-revision Confirm. Merged Voice plurals/aliases/modifiers, spelled
  numbers, seats, dietary facts/review, conservative similarity, typed fallback,
  live provider route and eighteen labeled synthetic audio fixtures/eval.
- Fixture migration: retain `the_bulldozer`/`the_backhoe` IDs from canonical menu.
  Explicitly updated Voice expected IDs in tests, manifest and generator; original
  spoken text/audio stays unchanged. Recomputed MOCK scorecard proves parser/
  scoring plumbing, not microphone or real-world STT quality.
- Source conflicts resolved: mvp/domain.py/voice.py, menu fixture, frontend
  app.js/index.html/mvp.css. Auto-merged contracts/API reviewed to preserve both
  seams. Root owns .env/README/shared docs plus server.py/demo_auth.py and global
  auth/deployment wiring. Locally those doc conflicts use HEAD just for testing;
  they must not replace root's integrated docs.
- Live transport: browser AudioContext + ephemeral mono PCM16 at 16kHz, with local
  resampling in voice-audio.js. ScriptProcessor is a replaceable producer seam;
  no MediaRecorder/WebM dependency. Server declares matching Deepgram encoding,
  sample_rate/channels and bounds even PCM length, per-message bytes, cumulative
  sample duration, stream wall time and real-time pacing with a one-second burst.
  Browser microphone support/secure context/provider availability still need
  actual device verification; a configured status is not proof of availability.
- Budget: thread-safe RLock protects accounting; each active stream reserves
  remaining daily seconds until finish. Provider failures charge reserved allowance
  conservatively; provider-reported usage is preserved. In-memory budget resets
  on process restart, so this is not a durable prepaid billing guarantee.
- Tickets: credential-gated HTTP issue endpoint requires a demo session. Server
  ticket JSON carries order_id/menu_revision; kitchen carries menu_revision. The
  ticket copies the exact pinned menu for provider keyterms. WebSocket uses both
  `ticket` and `session_id` query parameters; wrong/missing session fails before
  rightful ticket consumption. IP is rate metadata only, not authentication,
  because Vercel HTTP proxy and direct Fly WebSocket can have different addresses.
- Frontend runtime: hosted empty API base uses `??`, so requests stay same-origin.
  Full `window.DIG_IN_VOICE_WS` points at the direct WebSocket endpoint; root owns
  its config. Shared HTTP requests may use the existing in-memory Basic fallback.
  API link points to /api/v2/contracts. No provider key belongs in browser config.
- Capture safety: pin actor/session/draft ID/revision/menu/view at start; validate
  after ticket, permission, socket and audio-resume awaits and before transcript
  application. Cancel on view/session/draft changes and stale revisions. An old
  startup promise cannot clear a newer hold. Limit/error/done/close stops tracks/
  audio input even if the hold button remains pressed. Confirm stays human-only.
- Dietary safety: unattached notes remain structured review evidence. They cannot
  be dismissed without choosing a saved dish; attachment preserves the note in
  line.requests and clears an opt-in dietary reminder correctly. Attached review
  flags bind matched output lines (not skipped raw clause indexes). Explicit
  plural kitchen start commands clarify instead of silently starting one unit.
- Privacy: no raw transcript/audio retention in v2 state/analytics. Provider
  request opts out of model improvement and redacts usage keyterms. Metadata still
  exists; claims do not imply provider/network erasure. Error logs avoid raw
  provider exception bodies. Legacy live capture remains root's deployment scope.
- Checks: full backend suite 185 passed; Node22 syntax and all 25 frontend cases
  passed. Eighteen-clip MOCK evaluation passed18/18. Scoped Ruff lint/format passed.
  Provider transport tested with fake Deepgram, including invalid PCM/rate/session,
  quotas, stale menus and dietary gates. No new paid live call or physical mic/
  headphone/device validation performed by this lane. Root owns the minimum
  separately authorized synthetic live probe after secure credential access.
- Official implementation references: [Deepgram encoding](https://developers.deepgram.com/docs/encoding),
  [keyterms](https://developers.deepgram.com/docs/keyterm),
  [usage redaction](https://developers.deepgram.com/docs/redact-usage).
  The mutable-menu keyterm request has a conservative400-byte aggregate budget
  plus term-count cap and grammar priority; provider limits may still reject a
  request and must fail back to text/taps without bypassing human review.
