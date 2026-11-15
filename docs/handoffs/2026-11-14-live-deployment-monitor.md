# Post-push live deployment monitor

- Base: main `bfc3562`; branch `codex/live-deployment-monitor`.
- User requested live-site monitoring after pushes. Menu/Core owns workflow/docs;
  backend agent owns reusable probe/poller/tests. Astra reviewed both seams.
- Implemented `scripts.monitor_deployment`, reusing the existing read-only smoke
  checks. Bounded attempts/intervals, early credential-configuration failure,
  sanitized JSON and temporary/ignored report destinations prevent silent green
  results or capture/credential disclosure. Existing smoke CLI behavior remains.
- Added `live deployment checks` workflow on main pushes and manual main runs.
  It checks out the eligible main commit, uses fixed production domains and
  accepts no deployment payload URL/ref or PR event. Job-level concurrency keeps
  eligible checks from overlapping. Three attempts,30s pauses,12-minute job cap.
  Manual rerun is required after an independently published Fly/Vercel release.
- Only demo login credentials are needed as Actions secrets; no Deepgram key,
  platform deployment token, paid call, order mutation or audio/video is used.
  No secrets were copied during implementation. Repository secret inventory was
  empty at this checkpoint; authenticated Actions setup requires explicit approval
  to copy the local demo credentials to that additional secret destination.
- Tests: **282 backend passed**, including **37 focused probe/monitor cases**.
  Ruff lint/format, YAML/main-only trigger/permissions review and whitespace pass.
  Astra independently passed37focused cases and cleared the source.
- Actual bounded live check used the ignored local demo credentials for two GET
  attempts. It correctly exited nonzero: frontend503, backend health404 and older
  unprotected snapshots without required menu revision. No raw response content,
  credential value or exception text entered the report.
- CV/frontend/legacy source is unchanged;
  the configured full CI is checked before merge. Source acceptance and live
  release failure remain separate statuses.
- Remaining release owner: configure matching Fly/Vercel secrets, publish updated
  backend, then run the monitor plus hosted/browser/hardware acceptance. Monitor
  success is HTTP readiness, not deployed SHA proof or physical/provider accuracy.

See [LIVE_MONITORING](../LIVE_MONITORING.md) for operation and limits.
