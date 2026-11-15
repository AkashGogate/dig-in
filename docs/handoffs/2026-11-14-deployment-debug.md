# Deployment debug and recovery from a signed-in machine

Date: 2026-11-14 America/Chicago. Source inspected: merged main `30af7c3`.
This is a deployment configuration/publication diagnosis, not a claimed repair.
No application code, auth weakening, cloud secret update or production deployment
was performed during this debug pass.

## Confirmed findings

| Surface | Actual result | Required action |
| --- | --- | --- |
| Vercel public root | 503 with exact body `Demo access is not configured.` | Set both production DEMO_AUTH_USER/PASS for the existing Vercel project, then create a new production deployment |
| Fly health | `/healthz`404 | Publish the integrated root-context backend image |
| Fly OpenAPI | 200 without auth; missing `/healthz`, `/api/v2/menu/prepare`, `/api/v2/menu/extract`, `/api/v2/cv/context`, `/api/v2/voice/ticket` | The served app is older than the integrated API; configure demo credentials and deploy current main |
| Frontend API proxy | 200 with older snapshot lacking menu_revision | Routing reaches an API, but it is not the required release; deploy Fly before accepting frontend readiness |
| Local deployment access | flyctl reports no access token; Vercel reports logged out; no FLY_API_TOKEN/VERCEL_TOKEN in the local configuration | Finish platform operations using a signed-in account with access to these existing apps |

Vercel's current middleware returns that exact503body only when either demo
credential is absent. The backend route fingerprint proves the public API does
not match the source; its exact deployed Git SHA/machine settings cannot be
inspected from this logged-out machine. GitHub deployment records alone are not
proof of the currently served Vercel/Fly build.

The two demo login secrets were configured in **GitHub Actions** with explicit
user approval. That configures authenticated monitoring only. It does not copy
the secrets to Fly/Vercel. The Deepgram key was not copied to GitHub Actions.

## Recovery order

1. Pull reviewed source into a clean checkout:

   ```sh
   git switch main
   git pull --ff-only origin main
   git rev-parse HEAD
   ```

   Use current main, not the earlier codex/application-integration branch.
   Actual `backend/.env` is intentionally ignored and will not arrive through
   Git; obtain its values through the existing local secret store/secure channel.
   Do not paste values into Markdown, shell arguments, screenshots or chat.

2. Verify account access with `flyctl auth whoami` and `vercel whoami`.
   If needed, sign in interactively using `flyctl auth login` / `vercel login`.
   Access must include Fly app `frictionless-kitchen` and Vercel project
   `frictionless-kitchen-frontend` in scope `akash-s-team4`.

3. Configure matching DEMO_AUTH_USER and DEMO_AUTH_PASS on both platforms.
   For Fly, `flyctl secrets import --app frictionless-kitchen --stage` reads
   NAME=VALUE pairs from stdin and stages them for the next deploy. Supply only
   intended values using the secret store, not an unreviewed whole env file.
   For Vercel, use production project secrets through the dashboard or the CLI's
   stdin/prompt path (`vercel env add NAME --environment production --sensitive
   --project frictionless-kitchen-frontend --scope akash-s-team4`). Existing values
   can be updated deliberately; do not expose them with `--value` or `--env` args.
   Env changes require a new production deployment before validation.

4. Publish Fly **from the repository root**, where Dockerfile and fly.toml live:

   ```sh
   flyctl deploy --app frictionless-kitchen --config fly.toml --ha=false
   flyctl status --app frictionless-kitchen
   flyctl checks list --app frictionless-kitchen
   ```

   Verify one warm machine/worker and a passing public minimal `/healthz`.
   Existing extra machines are not removed by --ha=false; review them rather
   than blindly deleting. Restart loses in-memory demo state. This image uses
   the canonical app and packages the owning CV event contract, not camera runtime.
   Keep live voice off until basic readiness passes, then deliberately configure
   the provider key/mode and budget if real microphone capture is wanted.

5. Inspect actual Vercel project settings before deployment:

   ```sh
   vercel project inspect frictionless-kitchen-frontend --scope akash-s-team4 --json
   ```

   Required project Root Directory is `frontend`, Node22, Other framework, locked
   npm install and no app build command. With that root setting, deploy the
   checkout from the repository root; avoid a nested frontend/frontend upload:

   ```sh
   vercel deploy --prod --project frictionless-kitchen-frontend --scope akash-s-team4
   ```

   The frontend's vercel.json rewrite must target the updated Fly domain. Publish
   the existing project; do not create a temporary/unclaimed replacement site.

6. From backend/, with the local credential file available:

   ```sh
   uv run --env-file .env python -m scripts.monitor_deployment --attempts 3 --interval-seconds 30
   ```

   Require health200, unauthenticated401 for protected surfaces, authenticated200,
   canonical menu revisions through both domains and valid voice status. Once
   real voice is configured, add `--require-live-voice` (status only; no paid call).
   Run [live deployment checks](https://github.com/AkashGogate/dig-in/actions/workflows/live-deployment.yml)
   manually from main after external publication; main pushes also trigger it.

7. Complete hosted browser login, Server→Confirm→Kitchen→pickup, targeted summary,
   PDF/photo upload/correction/encoding/activation and direct WebSocket checks.
   Use simulated records; keep physical CV/noisy-room microphone/phone/output
   claims separate. Do not disable auth to make a failing probe green.

## Validation and preservation

The exact application source already passed402Python and62frontend tests,
lint/format, hygiene, secret scans and container smoke. This debug handoff changes
documentation only. Original untracked duplicate files are preserved and excluded.
No new provider charge or deployment was incurred.

CLI options were checked against installed flyctl/Vercel65.16.0. Platform
references: [Fly deploy](https://fly.io/docs/flyctl/deploy/),
[Vercel deploy](https://vercel.com/docs/cli/deploy),
[Vercel monorepos](https://vercel.com/docs/monorepos/monorepo-faq).
