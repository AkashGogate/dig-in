# Fly / Vercel application deployment

Release source: merged `main` (includes the application, UI and monitor PRs).
Do not deploy the older `codex/application-integration` branch by itself.
User-supplied domains:
[frontend](https://www.frictionless-kitchen.akashgogate.com) and
[backend](https://api.frictionless-kitchen.akashgogate.com). Source configuration
does not establish what is deployed. STATUS records observed results.

## Runtime

Vercel project root is **frontend/**, framework Other, Node22, `npm ci`, no app
build command, output directory `.`. `middleware.ts` runs on Node and guards every
static page/asset. `vercel.json` rewrites `/api/*` to the backend domain. Browser
HTTP stays same-origin; the proxy must forward Authorization, which Fly validates
again. API uploads bypass Routing Middleware's body limit and remain authenticated
and bounded by the backend (8MiB). Real hosted proxy/upload behavior needs testing.

`window.DIG_IN_VOICE_WS` is the full public `wss://.../api/v2/voice/stream` endpoint
directly on Fly. Authenticated HTTP issues a short-lived, one-use ticket bound to
the demo device session and pinned menu. WebSocket query parameters carry ticket
and session_id, never a provider key. The image disables Uvicorn access logs to
avoid query-string ticket logging. HTTP quotas can group devices behind a proxy IP.

Fly uses the **repository root** Dockerfile/fly.toml. Older backend-only deploy
entrypoints moved here because the image needs the CV lane's owning event source.
OpenCV/MediaPipe/cameras run in a separate opt-in sidecar, not the API image.
Standalone kitchen-backend is a preserved regression target, never a second app
writer. See [CV integration](../cv-service/V2_INTEGRATION.md).

Use one Fly machine, one region and one Uvicorn worker. Auto-stop and auto-start
are false in source; deliberately start the warm machine before the demo.
`--ha=false` prevents adding a standby on initial deploy but does not remove
existing machines. Verify actual count is one. Restart loses orders, sessions,
budget, dedup receipts and pending outbox. Basic demo access does not provide
durable identity, private role-isolated snapshots or multi-worker persistence.

## Secrets

Set the SAME `DEMO_AUTH_USER` and `DEMO_AUTH_PASS` as server-side secrets on Vercel
and Fly. Both must exist. Frontend missing configuration fails503; Fly/partial
configuration fails401. All HTTP data/commands/schema require login. `/healthz`
alone is public/minimal. CORS preflight contains no data. Local development allows
both credentials unset unless DIG_IN_REQUIRE_AUTH=1. No default password ships.

Keep `.env` local/ignored with restricted file permissions. Never paste keys into
chat, Markdown, URLs, screenshots or shell history/arguments. Platform secret
facilities own deployed values. `.env.example` contains names and blank values;
browser config contains only public addresses.

Live voice defaults OFF. Deliberately configure DIG_IN_VOICE_LIVE=1 and
DEEPGRAM_API_KEY on Fly to enable. Backend reserves concurrent quota and bounds
PCM sample duration, bytes, pacing and stream time. Provider failures charge
conservatively; budget resets on restart, so set provider account limits too.
Legacy binary audio is disabled to prevent bypassing v2. Semantic embeddings are
a separate paid opt-in; local lexical vectors need no key.

Production HTTP uses the rewrite. For cross-origin development set
DIG_IN_CORS_ORIGINS to exact allowed origins; never publish a key in config.js.

## Release checks

For the current diagnosed failures and the signed-in-machine recovery sequence,
start with [deployment debug handoff](handoffs/2026-11-14-deployment-debug.md).
GitHub Actions secrets configure monitoring only; they do not configure either
Fly or Vercel. Production demo credentials must be set on both platforms too.

1. Inspect Git/worktrees and handoffs. Integrate reviewed refs in isolation. Run
   locked backend/CV/kitchen suites, Node tests, hygiene and secret scanning.
2. Configure platform secrets and Vercel root first. Build the root image. From
   the repository root use `fly deploy --ha=false`; restarting loses demo state.
   Deploy matching reviewed source to Vercel and verify one Fly machine/worker.
3. From backend/, with credentials in the environment, run
   `uv run python -m scripts.smoke_deployment`. This makes only read requests and
   prints outcomes, never credentials/state. It checks login refusal/success,
   health, proxy and menu revision. Matching revisions alone do not prove a
   single process: verify the configured target and actual instance count.
4. Hosted browser: sign in, upload a synthetic PDF/photo, correct dishes, encode,
   review and activate. Preserve an older draft. Exercise Server→Confirm→Kitchen
   ack→per-unit ready→targeted update→Server pickup/summary, stale/retry paths and
   camera-blocked tap recovery. Label test records simulated.
5. With provider access, first send one short synthetic clip through v2, paced
   PCM16/16k mono. Test physical mic and the 18-clip evaluator separately; record
   actual seconds, estimate and outcomes. Transcript accuracy differs from review
   correctness. Provider usage metadata still exists despite retention controls.
6. Explicitly calibrate the real CV rig/hand model; test empty/single/multiple
   plates, hand, blockage/offline/recovery and stale assignment. Synthetic tests
   do not establish physical detection, lighting or noisy-room performance.

No finite test set guarantees a failure-free demo. Credentials, real devices,
container/host routing and cloud coverage must not be inferred from config flags.
Official references: [Vercel middleware](https://vercel.com/docs/routing-middleware),
[rewrites](https://vercel.com/docs/routing/rewrites),
[Fly configuration](https://docs.fly.io/reference/configuration).
