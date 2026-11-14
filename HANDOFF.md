# HANDOFF.md

## Goal
Build kitchen-copilot (voice kitchen fire-call agent) per PROJECT_SPEC.md for Deepgram application; backend+frontend+tests+hosting scaffold+CI built across prior sessions. Now in the middle of production deploy + custom domain setup.

## Current State
- Backend LIVE on Fly.io: https://frictionless-kitchen.fly.dev (confirmed healthy via /scenarios -> 200; root "/" 404 is expected/by design, no route defined there).
- Frontend LIVE on Vercel: https://frictionless-kitchen-frontend.vercel.app (project "frictionless-kitchen-frontend", Akash's Team, root dir frontend/, static HTML/JS/config.js, no build step).
- fly.toml and the pythonpath CI fix are already committed (in commits d2896e5 / eb8e75d) - not open items anymore.
- TWO fixes still uncommitted/unpushed (carried over, unchanged this session):
  1. backend/eval/deepgram_prerecorded.py - utterances=true fix, verified against live Deepgram API.
  2. backend/app/session.py - per-IP hourly rate limit (10/hr) + global daily session cap (200/day), verified 15/15 pytest pass.
- UNRESOLVED scope question (carried over, still no answer): async kitchen-to-server "heard" paging/comms system - v2 of kitchen-copilot or separate project? Logged to docs/FUTURE_IDEAS.md as brainstorm only, NOT built.
- Custom domain work (in progress, user driving the UI, Claude guiding step by step via screenshots):
  - Target: https://www.frictionless-kitchen.akashgogate.com for the frontend (user originally wrote an invalid underscore version, corrected to hyphen), with a sibling api.frictionless-kitchen.akashgogate.com planned for the backend (not yet started - Fly side has NOT been touched this session).
  - Domain is on Squarespace DNS. User added www.frictionless-kitchen.akashgogate.com in Vercel's project Domains settings (NOT by editing the existing auto-assigned frictionless-kitchen-frontend.vercel.app entry - correctly added as a new entry instead, per last session's guidance).
  - First DNS attempt: Vercel showed "Generating SSL Certificate" (looked like it was working), but then flipped to "DNS Change Recommended" - Vercel wants a project-specific CNAME value, not the generic `cname.vercel-dns.com` one. Correct value per Vercel's UI: `c4f6c399d713d30c.vercel-dns-017.com` (advised user to use the value shown/copied directly from their own Vercel screen, since these are assigned per-domain/per-project and this exact string is specific to their setup - treat it as reference, re-check their live screen if anything is re-done).
  - Told user to EDIT the existing CNAME record in Squarespace for host `www.frictionless-kitchen` to that value (not add a duplicate second record), and to enter it WITHOUT the trailing period Vercel's copy button includes (Squarespace's simplified DNS editor appends the FQDN dot itself; typing it manually can cause issues).
  - Not yet confirmed whether this second DNS edit resolved - awaiting user to save in Squarespace and click Refresh in Vercel.
- frontend/config.js STILL hardcoded to `http://localhost:8000` - the deployed Vercel frontend (at either the vercel.app URL or once the custom domain works) does NOT yet actually talk to the live Fly backend. Offered to point it at the working https://frictionless-kitchen.fly.dev URL as an interim fix so the demo works end-to-end today, independent of the custom-domain DNS work - user has not yet said yes/no to this.

## Files in Flight
- backend/eval/deepgram_prerecorded.py - utterances=true fix, uncommitted, verified against live API.
- backend/app/session.py - rate limit additions, uncommitted, tests pass.
- frontend/config.js - NOT yet edited; still points at localhost, blocking real end-to-end functionality on any deployed URL.
- backend/app/server.py - CORS narrowing from `allow_origins=["*"]` to the real frontend domain, not yet done (waiting on which domain becomes final).
- docs/FUTURE_IDEAS.md - async kitchen-to-server comms brainstorm (carried over, unchanged).
- HANDOFF.md, feedback.md - rewritten each Stop hook.

## Changed This Session
- No code changes. Pure DNS/hosting-UI guidance: Vercel domain-add confirmation, diagnosing a "DNS Change Recommended" CNAME mismatch, correcting the CNAME value and trailing-dot question for Squarespace.

## Failed Attempts
- First Squarespace CNAME value used by the user (likely the generic `cname.vercel-dns.com` suggested earlier) did not satisfy Vercel for this specific domain - Vercel wanted a project-specific target (`c4f6c399d713d30c.vercel-dns-017.com`) instead. Lesson: don't assume the generic Vercel CNAME target is always correct - always read the exact value off the live "DNS Change Recommended" panel for that specific domain.

## Next Step
- Confirm the corrected CNAME (no trailing dot) was saved in Squarespace and that Vercel's domain entry flips to "Valid Configuration" after Refresh.
- Decide/execute: point frontend/config.js at https://frictionless-kitchen.fly.dev now (interim, works immediately) vs. waiting for api.frictionless-kitchen.akashgogate.com (cleaner, not started yet - would need `fly certs add api.frictionless-kitchen.akashgogate.com` via local flyctl, then another Squarespace DNS record).
- Once a final backend URL is settled, narrow CORS in backend/app/server.py from `["*"]` to the real frontend origin.
- User to add a small Deepgram prepaid credit top-up (e.g. $10) as the real spend ceiling - still pending.
- User to answer: is the async server-comms paging idea v2 scope or a separate project? - still pending.
- User to commit/push the two remaining uncommitted fixes (utterances=true, session.py rate limits), then verify green CI.
- caveman:compress invoked per Stop hook but does not exist as a real skill (confirmed again, repeatedly across many sessions) - cannot compress via this mechanism.
