# Final real-provider voice validation before main merge

- Owner: Menu/Core integration; Astra performed independent read-only source
  review, and the backend lane reran focused credential-free regressions.
- Tested application source: `5b956b1`, `codex/application-integration`.
- Date: 2026-11-14 America/Chicago.
- Scope: authenticated local v2 HTTP + WebSocket relay to actual Deepgram nova-3,
  with synthetic speech, canonical Server/Kitchen commands and explicit human
  confirmation. A separate fresh backend preserved the existing demo's state.
- No application source change was required by this validation.

## Actual live result

Four short synthetic clips used 6.5969375 seconds of PCM audio; adapter usage
reported 6.6 seconds and estimated USD 0.0008 at its configured rate. Raw audio,
transcripts, credential values and bearer tickets are not included in this report.

| Scenario | Result |
| --- | --- |
| Server order | Correct dish and quantity; confidence 0.8886719; created only an editable draft |
| Short Kitchen acknowledgment | Confidence 0.7158203; required clarification; no automatic food-state change; explicit tap recovery worked |
| Kitchen start | Confidence 0.93359375; live command started the intended physical unit |
| Clearer Kitchen acknowledgment | Confidence 0.94970703; recognized table two and acknowledged its single submitted order without clarification |

The initial three-clip acceptance script passed all 30 assertions; the fourth
diagnostic verified a successful actual-provider acknowledgment. Additional
checks rejected unauthenticated state access, rejected reuse of each initial
ticket, rejected voice-sourced Confirm, accepted explicit tap Confirm, kept the
transcript out of the snapshot, closed every provider stream and stayed inside a
one-minute server-side budget. Confidence values are provisional review hints,
not calibrated probabilities or microphone accuracy measurements.

## Other submission evidence

- Focused Voice/live relay/fallback/dietary/menu/Core/application/auth suite:
  **96 passed** on the exact source tip, without paid calls.
- Full push and PR CI on `5b956b1`: passed all three jobs, including 365 Python
  tests, 55 frontend tests, lint/format, hygiene and container build/HTTP smoke.
  [Push CI](https://github.com/AkashGogate/dig-in/actions/runs/43663864467),
  [PR CI](https://github.com/AkashGogate/dig-in/actions/runs/43663869475).
- Hygiene: 286 indexed paths; credential examples blank and ignore probes pass.
  Gitleaks: 44 locally reachable commits scanned, zero findings.
- Independent Astra review found no must-fix source issue in ticket/session/menu
  pinning, PCM/pacing/time caps, quota reservations, confidence review or browser
  cleanup. The open PR inventory contained PR #1 only at this checkpoint.

## Local live setup and remaining limits

From `backend/`, load the ignored local configuration before server import:

```sh
DIG_IN_VOICE_LIVE=1 uv run --env-file .env uvicorn app.server:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

The environment needs `DEEPGRAM_API_KEY` and matching demo credentials. Restart
after changing mode/limits. Use localhost or HTTPS for browser microphone access;
never place a provider key in frontend configuration. New operator pages link
the full workbench for deliberate microphone capture and complete review.

This is actual provider integration testing with synthetic speech, not physical
microphone/noisy-room, hosted WebSocket/proxy or device-output validation. One
phrase needing clarification demonstrates why review and tap recovery remain
necessary. Physical CV, optional remote semantic vectors and live Databricks were
not tested here. Hosted release remains assigned to the signed-in deployment
owner; see [deployment handoff](../DEPLOYMENT_HANDOFF.md).
