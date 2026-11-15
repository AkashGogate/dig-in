# Production handoff to the signed-in deployment agent

The user authorized republishing Fly and Vercel, then explicitly assigned the
actual release to another agent with account access. This integration session
made no production changes. Fly/Vercel sign-in attempts were canceled cleanly.
No passwords or tokens should be sent through chat.

## Source and tools

Review PR https://github.com/AkashGogate/dig-in/pull/1, branch
codex/application-integration. Fetch latest branch and read STATUS and
DEPLOYMENT; verify the exact tip CI instead of using an old result. Preserve
main/teammate branches and any local edits. The local shared workspace is already
on the integration branch; the reviewed execution clone is under /private/tmp.
The user's backend/.env is ignored and owner-readable, with DEEPGRAM_API_KEY and
DEMO_AUTH_USER/PASS. Read values locally without printing/committing them.

Fly CLI is installed at /Users/allen/.fly/bin/flyctl. Vercel65.16.0 is installed in
/private/tmp/dig-in-submission-tools/vercel-cli/node_modules/vercel/dist/vc.js;
Node22 is /private/tmp/dig-in-submission-tools/node-v22.23.5-darwin-arm64/bin/node.
These temporary tool paths are this machine only. Neither CLI was authenticated
by this session; use an account with deployment access to the existing apps.

## Existing targets and important ordering

- Fly app frictionless-kitchen, backend api.frictionless-kitchen.akashgogate.com.
- Vercel akash-s-team4/frictionless-kitchen-frontend,
  frontend www.frictionless-kitchen.akashgogate.com.
- Configure matching DEMO_AUTH_USER/PASS on both platforms before release. Use
  platform secret facilities/stdin, not values in CLI arguments or shell history.
  Backend requires credentials on Fly; frontend middleware fails503 if missing.
- Root Dockerfile/fly.toml are authoritative. The former backend-only deployment
  entrypoints moved because the API image packages cv-service's owning event model.
  Check any GitHub/Fly build-directory setting before relying on auto deployment.
- One Fly machine/region/worker; auto-stop and auto-start false in source. Verify
  actual machine count and start it deliberately. --ha=false does not remove old
  extra machines. Deployment/restart loses in-memory sessions/orders/outbox.
- Vercel project root frontend/, Node22, npm lockfile, no app build step. Read the
  project's actual settings before linking/deploying; avoid uploading a nested
  frontend/frontend directory. Vercel configuration proxies /api/* to Fly; it
  does not serve an independent backend. Production needs the same reviewed tip.
- DIG_IN_VOICE_LIVE defaults0. Configure the key and explicitly enable only if
  real voice is desired, with budget/provider limits. Keep live CV off until real
  camera calibration and hand model validation; the CV sidecar is not in API image.

## Verification and known gaps

Before release, production backend state returned200withoutlogin and health404;
production frontend root200withoutlogin and /api/v2/state404. The integration
preview built successfully but redirects to VercelSSO, so app-level hosted login,
API rewrite, WebSocket and large upload were not verified. Do not call them passed.

After publishing, run backend/scripts/smoke_deployment.py with credentials in the
process environment. Verify unauthenticated401, valid login, publicminimalhealth,
proxy, matching menu revision, one machine, direct session-bound voice endpoint
and a synthetic PDF/photo upload/correction/encode/activation in the hosted app.
Test both staff roles and uncertainty/retry on the public domains. Use one short
synthetic voice clip first; this branch already has bounded real-provider evidence
in STATUS, so do not repeat a large paid matrix without a reason.

Physical CV alignment/hand detection/reconnect, actual staff/noisy-room mic,
phone/earpiece/physical printer and live Databricks remain unverified. Global demo
snapshots are not private role isolation; state/dedup/budgets are not durable.
Keep these limits literal in the release handoff and update STATUS with exact
new evidence. Never rewrite the old live-eval artifact as a new successful run.
