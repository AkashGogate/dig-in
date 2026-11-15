# Unified application integration handoff

- Base: menu/service9d3face37fa116348943955606a8edcdacc062e8.
- Incoming Voice9af39dcfe7314485be3855944c6817b3826d6ab5 and
  CV3b0d0a1564674b6a6f190c463cb70661da1433b0 merged with ancestry preserved.
- Branch: codex/application-integration. Main and teammate branches are preserved.
  Work used isolated clones; root integrates reviewed lane files and deployment.
- Supervision: user-requested Astra maximum reasoning audited both lanes and root;
  all routed source blockers resolved, including PCM quotas/device tickets, dietary
  attachment/deletion, real hand/calibration/confidence/dwell and CV recovery gates.
- Architecture: one Restaurant owns menu/orders/dishes/zones/events/outbox. Voice
  emits editable drafts/intents. CV uses owning producer schema then canonical
  versioned commands. Independent kitchen-backend remains a legacy test target.
  Existing structured/OCR menu correction, vectors, activation/pinned drafts and
  both role journeys/updates/explicit summary print/speech are preserved.
- Root additions: all-HTTP demo gate/minimal health, Node Vercel static gate and
  same-origin API rewrite, public direct Fly WS endpoint, root image/Fly config,
  read-only deployment probe, hash-only branch watcher, integrated CI and docs.
  Old backend-only deployment entrypoints moved to root for CV contract packaging.
  Two real incoming calibration images are absent from the tip and ignored locally.
- Evidence:207app+47CV+44legacy kitchen Python tests;29Node cases;54Python files
  lint/format; fresh HTTP MVP smoke; real desktop browser ServerConfirm→Kitchen
  ack/twozones/start/partialstableplate/requestedsummary. Voice lane MOCK18/18;
  fakes do not establish speech quality. One existing Starlette warning remains.
- Hosted read-only findings: backend state200unauth, health404; frontend root200
  unauth, frontend API404. Source fixes must be deployed with matching secrets.
  Current root local .env was unavailable during checks. No paid live provider,
  physical camera/mic/phone, noisy kitchen, real printer/earpiece, live Databricks
  or durable/multi-worker validation. Container/hosted CI results are recorded in
  STATUS when available. No finite suite guarantees a failure-free live demo.
- Active hourly local heartbeat watch-dig-in-integration-branches compares hashes;
  unchanged is cheap. Changed refs use isolation, scoped review and required tests.
  It does not automatically deploy/enable billable services; app/machine must run.
- Agent entry: AGENTS→INDEX→STATUS→AGENT_TASK_MAP/INTEGRATION_GUIDE→DEPLOYMENT;
  lane details in voice-application-integration and cv-application-integration handoffs.
