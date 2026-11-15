# End-to-end local demo acceptance

- Owner role: Menu/Core integration; backend acceptance delegated to the service
  backend agent, with browser/menu acceptance performed in the main lane.
- Branch / tested code: `codex/application-integration`, documentation tip
  `5ea063c` (application source unchanged from the passing integrated checkpoint).
- Scope: fresh local shared-API acceptance and actual browser menu controls.
  No implementation changes or contract changes were needed during this pass.

## Checks actually run — 2026-11-14 America/Chicago

**24 of 24 real HTTP checks passed**, run `e2e-http-a342663e93`:

- Three staff sessions; spoken table mismatch and unknown dish require review.
  Unreviewed, stale-revision, false-confirmation and voice-sourced submissions
  were rejected. Current-revision human confirmation and exact replay passed.
- Submission stayed distinct from kitchen acknowledgment. Two physical units
  atomically reserved distinct zones, followed by explicit start.
- Stale CV capture bindings were rejected; short dwell and hand evidence did not
  mark dishes ready. Partial readiness produced no all-ready alert; completion
  produced exactly one.
- Kitchen updates reached the owning server's scoped summary. Recipient and
  revision guards, acknowledgment retry, and read-only role summaries passed
  without changing food stages.
- Pickup freed zones and made historical pickup requests non-actionable.
  Delivery/update resolution closed both acceptance tickets. Raw capture text
  stayed out of drafts/events, and explicit update notes stayed out of events.

**Actual browser PDF flow passed:** upload a synthetic two-dish menu, extract
editable proposals, remove a heading falsely proposed as a dish, prepare local
encodings, explicitly confirm review, then activate. Activation stayed disabled
until review. This demonstrates the correction gate; extraction is not assumed
to be flawless.

**Actual photo OCR endpoint passed:** a readable synthetic PNG returned HTTP 200
with reviewable proposals. An earlier black/unreadable fixture returned 422.
This photo check exercised the API; the browser chooser was exercised with PDF.

**Menu replacement compatibility passed:** a voice-created draft matched the
new Tomato Soup menu, while an existing ticket retained its eight-dish menu
snapshot. Restoring the original eight-dish menu preserved the replacement-menu
draft's pinned revision. The original demo ticket was preserved and the active
demo menu restored. Acceptance tickets were closed.

## Evidence boundaries and next owner

The local pass used real API state and OCR, deterministic voice input, local
lexical menu encodings, and simulated CV observations. No additional paid calls,
physical camera/microphone, external analytics or deployment occurred. Existing
CI evidence (365 Python tests, 53 Node tests and container smoke) remains linked
in STATUS; those unchanged suites were not rerun for this documentation update.

No blocking defect was found in these exercised paths. The deploying owner still
needs to verify hosted login, API proxy, WebSocket and upload limits after Fly/
Vercel release. Physical CV calibration, real room speech, phone/earpiece routing,
printing, optional remote semantic providers and live analytics remain separate
checks. See [deployment handoff](../DEPLOYMENT_HANDOFF.md) and
[acceptance map](../INTEGRATION_ACCEPTANCE.md).
