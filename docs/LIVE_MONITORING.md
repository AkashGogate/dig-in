# Post-push live readiness monitoring

The `live deployment checks` GitHub Actions workflow runs after a push to main
and on manual dispatch from main. It checks the two fixed production domains,
not a URL supplied by an event. Rerun it manually after an independently published
Fly/Vercel deployment finishes; a successful build alone is not a live pass.
PR, preview and arbitrary deployment-status events do not trigger privileged checks.

The workflow makes at most three read-only probe attempts with 30 seconds between
failures and a 12-minute job timeout. A newer trigger cancels the older monitor.
The probe checks minimal health, unauthenticated refusal, valid demo login,
frontend API routing, canonical menu revision agreement and voice-mode status.
It creates no session/order, uploads no menu, records no microphone/video and
makes no paid provider request. It does not deploy or change platform secrets.

## Credential setup

Authenticated checks need repository Actions secrets named `DEMO_AUTH_USER` and
`DEMO_AUTH_PASS`, matching the Fly/Vercel deployment. Missing configuration is an
explicit failure, never a green result. No Deepgram key is needed by this monitor.
The workflow checks out the eligible main commit, never a deployment payload ref, and
passes credentials only in the probe process environment. Reports contain check
names/statuses and sanitized errors, not credentials, bodies, notes or transcripts.

Use the Actions page to inspect `live deployment checks` and its job summary.
On manual dispatch, enable `require_live_voice` if the release must expose
Deepgram streaming mode. This verifies mode availability, not speech accuracy.

For a local check from backend/, with credentials in the environment:

```sh
uv run --env-file .env python -m scripts.monitor_deployment --attempts 3 --interval-seconds 30
```

CLI limits are finite: at most ten attempts, interval at most60seconds. Results
can be written with `--report-file` to an ignored output path. A zero exit means
all configured HTTP checks passed on one attempt; nonzero means the release is
not verified. A transient failure retries; absent credentials fail immediately.

## Release and ongoing limits

At implementation time the live frontend returned503 (`Demo access is not
configured.`), backend health404 and unprotected older snapshots. Monitoring
reports this gap; it cannot repair publication or missing platform secrets.
After the deployment owner publishes, rerun until healthy, then perform the
hosted Server/Kitchen, menu upload and direct WebSocket/browser acceptance in
[DEPLOYMENT](DEPLOYMENT.md). Physical CV/mic/output and actual provider quality
are separate checks. Passing matching menu revisions does not prove deployed
Git SHA, machine count or durable/private production identity.

GitHub documents [workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
and [Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).
