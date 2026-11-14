# Legacy context — archived 2026-11-14

Historical proposals and deployment reports, preserved from the starting checkout. These are not current requirements, verified deployment state, or permission to deploy. Current decisions are in `PROJECT_SPEC.md` and `docs/DECISIONS.md`. Some original documents contradict one another and actual code (for example Next.js vs static HTML, audio corpus present vs absent).


---

## Original PROJECT_SPEC.md

# Project Spec — Voice-Native Kitchen Operations Agent

Working name: kitchen-copilot (placeholder)
Author: Akash

## 1. The problem, precisely
Professional kitchens run on an existing verbal protocol — "calling the pass," "86 the salmon," "fire table 12" — because hands are full and the floor is too loud/fast to type or tap a screen. This project digitizes a behavior that already exists; it doesn't invent a new one.

What's missing today: verbal fire calls aren't captured anywhere. A mismatch between what was called and what the ticket says isn't caught until the wrong plate is already out. There's no timestamped record of calls, and no safety net for a misheard count beyond another human's attention — the one resource a loud kitchen doesn't have spare.

The governing test for every feature: remove the microphone — does the task still work, just worse (typing, tapping, writing)? If yes, cut it.

## 2. Why this, personally
Frustration with how easy it's become to do the bare minimum in food service, and real respect for kitchens that still put in the work. The throughline is cost, not front-of-house romance — lower error rates and less labor friction in the back of house is what lets a kitchen that cares charge less and still do it right. Scoped to the kitchen specifically — does not extend to customer-facing ordering.

## 3. Non-goals
- Front-of-house / table-side / customer ordering — already built and crowded (Tablevoice, PopID's Genius Handheld, SoundHound for Restaurants, ConverseNow, VoicePlug, Checkmate).
- Drive-thru / QSR ordering — Deepgram's own OfOne acquisition's lane.
- Any feature with a trivial non-voice substitute.
- Voice-stress/emotion-based inference of anything — not scientifically defensible, not in this project at any scope.

## 4. Core functionality (v1 scope)
1. Live fire-call capture — transcribe and structure spoken calls into order-line objects.
2. Mismatch detection — cross-reference spoken calls against the active ticket queue, flag discrepancies before the plate goes out.
3. Timestamped structured log — every call logged with speaker-turn attribution and timestamp, matched or not.
4. Noise-robust turn handling — tolerate overlapping/simultaneous calls plus ambient kitchen noise without breaking. This is the real technical difficulty of the project.

## 5. Success criteria
- Working pipeline: live or pre-recorded kitchen audio in → structured, timestamped, mismatch-flagged log out.
- Coval-based synthetic test suite with pass/fail scorecard and a documented failure-found-and-fixed story.
- A public, demoable surface with a safe fallback.
- An honest account of what breaks under hard conditions and what was done about it.

## 6. Target users / advertisable reach
Small/independent restaurant kitchens, reached through Akash's existing network — not an invented user base.

## 7. Alignment notes (Deepgram JD, for reference)
- Scoped project, shipped end-to-end — resist scope creep.
- Contribute to production Deepgram codebase — build on Pipecat, scope a real example/PR.
- Agentic tooling as default — use Claude Code throughout, keep notes on specific instances.
- Improve a workflow with AI tools — the Coval eval loop is this bullet.
- First-principles reasoning — design decisions defensible on their own terms, not copied from a competitor.


---

## Original HANDOFF.md

# HANDOFF.md

## Goal
Build kitchen-copilot (voice kitchen fire-call agent) per PROJECT_SPEC.md for Deepgram application; backend+frontend+tests+hosting scaffold+CI built across prior sessions. Now migrating repo from Frictionless-Kitchen to dig-in (github.com/AkashGogate/dig-in) and repointing Vercel/Fly deployments to the new repo, then finishing production deploy wiring (config.js -> live backend, Basic Auth on frontend).

## Current State
- Backend LIVE on Fly.io: https://frictionless-kitchen.fly.dev - Basic Auth gates /session/start (verified 401/401/200 for no-creds/wrong-creds/correct-creds), per-IP hourly (10/hr) + global daily (200/day) session caps deployed, Deepgram utterances=true fix deployed, 120s/2-concurrent caps unchanged.
- Frontend LIVE on Vercel at frictionless-kitchen-frontend.vercel.app AND custom domain www.frictionless-kitchen.akashgogate.com ("Valid Configuration").
- Git remote `origin` swapped from Frictionless-Kitchen.git to https://github.com/AkashGogate/dig-in.git (user confirmed: swap remote only, keep history).
- RECOVERED a rebase incident this session (see Failed Attempts) - local `main` now has: 585eab9 -> d2896e5 -> eb8e75d -> 8ed818e -> merge commit adc9906 (merging in dig-in's unrelated root commit cd44060, README conflict resolved keeping our README via -X ours). 49 tracked files, working tree clean except HANDOFF.md/feedback.md (expected, this hook).
- Local main is now AHEAD of origin/main (dig-in) by 5 commits - NOT YET PUSHED. User needs to run `git push origin main` themselves (push from this tool hangs on an interactive credential prompt - confirmed twice now).
- Submission/secret check re-run clean on the fixed tree: .gitignore present, backend/.env never in history and still gitignored, no tracked files >1MB, no hardcoded secret literals.
- Vercel/Fly repointing to dig-in: NOT YET DONE. Instructions given to user (Vercel: Settings -> Git -> disconnect/reconnect to dig-in, reset root dir to `frontend`; Fly: either relink GitHub auto-deploy to dig-in the same way, or just keep using `fly deploy -a frictionless-kitchen` manually from backend/ which doesn't care which repo is linked). User has not yet acted on either.
- Frontend still broken end-to-end in a real browser (carried over, unrelated to repo migration): frontend/config.js still hardcodes http://localhost:8000, and frontend does not yet send Basic Auth credentials to the backend.

## Files in Flight
- HANDOFF.md, feedback.md - rewritten/appended each Stop hook, currently the only modified files in the working tree.
- Carried over, still pending: frontend/config.js (hardcoded localhost), backend/app/server.py (CORS still `allow_origins=["*"]`), a login/Basic-Auth-credential-sending mechanism for the frontend - none touched this session.

## Changed This Session
- Swapped git remote origin to https://github.com/AkashGogate/dig-in.git.
- Ran `git push -u origin main` which hung on a credential prompt - killed via TaskStop.
- User ran their own rebase against the new remote (outside this tool) which went wrong: unrelated histories, `main` ended up pointed at just dig-in's bare README commit, working tree got wiped down to ~1 tracked file (though nothing was actually lost - old commits stayed reachable via a stash ref).
- Dispatched a fork agent to rebase+fix conflicts+submission-check; it correctly diagnosed the wipe, did NOT blindly fix it, and reported back precisely what was wrong and what was still recoverable.
- Recovered in the main thread: `git reset --hard 8ed818e` (restore full original history/tree), then `git merge cd44060 --allow-unrelated-histories -X ours` (merge in dig-in's root commit, keep our README on conflict) -> clean merge, verified log/file-count/status.
- Re-ran full submission/secret check on the recovered tree - clean.
- Popped the `handoff/feedback notes` stash back - restored HANDOFF.md/feedback.md edits cleanly.

## Failed Attempts
- `git push -u origin main` (this session, again) hung past timeout on what looks like an interactive credential/auth prompt with no TTY available - killed, handed back to user to run manually. Second time this exact failure mode has occurred.
- User's own `git pull --rebase origin main` against the newly-swapped dig-in remote failed badly: rebasing onto an unrelated-history initial commit left `main` pointed at just that bare commit and wiped ~48 tracked files off disk (recoverable - all old commits were still reachable via a stash ref, nothing GC'd). Root cause: rebasing across truly unrelated histories (different repos, no common ancestor) is the wrong operation - a merge with `--allow-unrelated-histories` is correct for "put two unrelated repos' histories together," not rebase. Lesson for future: when swapping a remote to a *different* pre-existing repo (not a fresh/empty one), check `git merge-base` first - if there's no common ancestor, use `git merge --allow-unrelated-histories` (or just reset to desired history and merge in the other side's content), never `git pull --rebase` or plain `git rebase`.

## Next Step
- User to run `git push origin main` themselves to land the recovered history (5 commits ahead) on github.com/AkashGogate/dig-in.
- User to repoint Vercel project's Connected Git Repository to dig-in (Settings -> Git), and either relink Fly's GitHub auto-deploy to dig-in or keep deploying manually via `fly deploy -a frictionless-kitchen` from backend/.
- Still pending from before: fix frontend/config.js to point at the live backend URL, add Basic-Auth-credential sending to the frontend, narrow CORS off `["*"]` once frontend origin is final.
- Still pending, unanswered across many sessions: async kitchen-to-server "heard" paging idea (docs/FUTURE_IDEAS.md) v2-or-separate-project question; Deepgram prepaid credit top-up; whether to gitignore HANDOFF.md/feedback.md going forward; confirm Fly auto-stop/auto-start machines are OFF.
- caveman:compress invoked per Stop hook but does not exist as a real skill (confirmed again, repeatedly across many sessions) - cannot compress via this mechanism.


---

## Original CLAUDE.md

# CLAUDE.md

Context for Claude Code when implementation starts. Read PROJECT_SPEC.md, docs/ARCHITECTURE.md, docs/TESTING.md first.

## Non-negotiable constraints
- No front-of-house/customer-ordering features — back-of-house only.
- No feature with a trivial non-voice substitute.
- No voice-stress/emotion-inference anything.
- Agent runtime needs a persistent-connection host, not plain serverless/Vercel.
- Public demo surface ships with both the live-mic path AND the test-scenario fallback, plus a session/time cap — never the live-mic path alone.

## Build order
1. `backend/` — Pipecat skeleton: audio in → Deepgram STT → call-parsing stub → log stub (single-speaker clean-audio happy path first).
2. `tests/` — synthetic clips, starting with the clean and two-overlapping-calls cases — don't wait for "done" backend to start this.
3. Mismatch detection against a mocked ticket queue.
4. Noise-robustness pass — layer in noise-bed and overlap cases, iterate.
5. Coval integration via Pipecat's documented connector.
6. `frontend/` — minimal demo page: live-mic button, test-scenario button, log display, mismatch display.
7. Hosting: backend to a persistent-connection host, frontend to Vercel; rate limiting and session caps before any link is shared.

When in doubt: apply the mic-removal test from PROJECT_SPEC.md §1. Flag ambiguity back to Akash rather than guessing scope.


---

## Original docs/TECH_STACK.md

# TECH_STACK.md

## Backend / agent runtime
- Python 3.11+
- Pipecat — audio pipeline orchestration (transport → VAD/turn-detection → STT → processing → TTS).
- Daily transport (WebRTC) via Pipecat's native integration.
- Deepgram STT (Nova-3 or Flux) with `diarize=true` for per-speaker-turn labels.
- Turn-taking: Pipecat's Silero VAD + Deepgram's end-of-utterance signal.
- Call-parsing layer: keyword/rule-based first pass (menu item names, quantities, station keywords) with a small LLM fallback for ambiguous phrasing.
- Ticket/order queue: mocked — a seeded SQLite table standing in for a real POS feed.
- Structured log store: SQLite via SQLAlchemy (async).
- API/WebSocket layer: FastAPI + WebSocket.
- TTS (mismatch alerts): Deepgram TTS (Aura).

## Frontend / demo surface
- Next.js/React. Minimal by design.

## Eval/testing
- Coval, via Pipecat's documented Coval integration.

## Hosting
- Backend: a persistent-connection host — Fly.io (default) or Render/AWS Fargate/EC2. Not Vercel for the agent runtime.
- Frontend: Vercel.

## Explicitly not used
- Vercel for the agent runtime.
- Any voice-stress/emotion/deception inference.
- Real POS/kitchen-display integration (mocked instead, stated honestly).


---

## Original docs/ARCHITECTURE.md

# ARCHITECTURE.md

## 1. Why hosting choice is a correctness issue
The agent needs a persistent, bidirectional, low-latency audio stream (Pipecat over WebRTC, Deepgram STT in the loop). Serverless functions (Vercel-style) have execution timeouts built for request/response, not held-open streaming — they'll work in short tests and die mid-session the first time someone holds a connection open past the timeout.

**Decision:**
- Agent runtime: a persistent-connection host — Pipecat Cloud/Daily's own hosting, or Fly.io, Render, or AWS Fargate/EC2.
- Static frontend: Vercel is fine — it only bootstraps the client, not the real-time stream.

## 2. Public demo surface — requirements
- 2.1 Abuse/cost exposure: per-session time cap, rate limit per IP/session, an easy kill switch.
- 2.2 Live-demo fallback: the demo UI must offer both "Use your own mic" (real live path) and "Play a test scenario" (pre-recorded, pre-validated clips through the same pipeline).

## 3. Data flow (v1)
```
[Kitchen mic/array] -> [Pipecat pipeline: turn-detection/diarization]
   -> [Deepgram STT: live transcript per speaker turn]
   -> [Call-parsing layer: structured order-line object]
   -> [Mismatch detector vs. active ticket queue]
        -> (mismatch) -> [alert: TTS back to line + kitchen display]
   -> [Structured log store: timestamped, speaker-attributed]
```

## 4. Noise-robustness — the actual hard problem
Everything upstream of call-parsing must tolerate overlapping/simultaneous calls, sustained noise beds, and short/shouted/truncated utterances.

## 5. Contribution angle
Scope at least one piece as a real example or small PR against the Pipecat repo.

## 6. Session/abuse controls (implemented in backend/app/session.py)
- `MAX_SESSION_SECONDS` hard cap per session, enforced server-side.
- Per-IP concurrent-session limit.
- A single `kill()` call tears down any session's pipeline immediately.


---

## Original docs/REQUIREMENTS.md

# REQUIREMENTS.md

One-sentence project statement: kitchen-copilot is a voice-native agent that listens to a live, noisy kitchen, turns shouted fire calls into structured records in real time, and catches ticket mismatches before the wrong plate goes out.

| # | Requirement | How kitchen-copilot satisfies it |
|---|---|---|
| 1 | Voice-native application | Every core function depends entirely on live spoken audio in a hands-busy, screen-free kitchen; no keyboard/button substitute. |
| 2 | Technically sound and impressive | Real-time, multi-speaker, overlapping-speech parsing under sustained kitchen noise, validated through a Coval-connected simulation suite with a documented failure-found-and-fixed story. |
| 3 | Live demoable | A hosted, public demo page lets anyone speak a live call themselves or trigger pre-recorded hard-condition test clips through the identical pipeline. |
| 4 | Benefits people | Cuts order errors and mental load on kitchen staff mid-service. |
| Bonus | Personal relevance | Motivated by Akash's own frustration with low-effort food culture and respect for kitchens that still do it right. |


---

## Original docs/USER_FLOW.md

# USER_FLOW.md

## Primary flow — live kitchen session
1. Session start (manual trigger for v1).
2. Kitchen mic/array streams continuously via Daily/WebRTC into Pipecat.
3. VAD + Deepgram end-of-utterance segment the stream into discrete turns.
4. Deepgram STT (diarized) returns text + anonymous speaker-turn label per turn.
5. Call-parsing layer extracts item, quantity, station/table reference.
6. Mismatch check against the mocked active-ticket queue — match logs clean, mismatch gets flagged.
7. On mismatch only: spoken TTS alert back to the kitchen and/or a flag on the live log.
8. Every call, matched or not, is written to the structured log with timestamp + speaker-turn id.
9. Frontend log updates live over WebSocket.

## Secondary flow — demo/test mode
1. Visitor picks "Use your own mic" or "Play a test scenario."
2. Own-mic path streams via the same Daily/WebRTC route as production; test-scenario path streams a pre-recorded synthetic clip through the identical pipeline.
3. Both produce the same live log + mismatch output, within the session cap from ARCHITECTURE.md.

## Tertiary flow — eval (not a live user flow)
Coval-connected suite runs the full synthetic test set against the deployed pipeline on demand/CI.


---

## Original docs/DEMO_PLAN.md

# DEMO_PLAN.md

Where: frontend on Vercel (public link), backend/agent runtime on Fly.io (or Render/AWS) — a real persistent endpoint, not localhost-only.

## How the live interview demo runs
1. Open with the Coval scorecard, not the mic.
2. Narrate one specific failure-and-fix from the eval history.
3. Live, own mic: a simple clean fire call, proving the end-to-end path works.
4. Live, hard case: "play a test scenario" to run a noisy/overlapping clip through the same live pipeline.
5. Let the interviewer try it themselves on the same public link.

## Fallbacks if something breaks live
The test-scenario path exists precisely for a flaky mic/network moment; keep a short screen recording of a full successful run as the last resort.

## What not to do
Don't open with an unscripted live mic attempt; don't imply real POS/kitchen deployment if it hasn't happened.


---

## Original docs/TESTING.md

# TESTING.md

## Why this is a first-class deliverable
The hardest part of this project — noise-robust, multi-speaker, overlapping call parsing — is exactly the kind of thing that "works in the quiet demo room, breaks in the real room." A rigorous eval suite is both the engineering safety net and the better live demo.

## 1. Tooling
- Pipecat → Coval integration (documented) — use it rather than building an eval harness from scratch.

## 2. Synthetic test set
1. Single clean call (baseline).
2. Two overlapping calls, different stations (core hard case).
3. Three+ simultaneous calls (stress case).
4. Call against a sustained noise bed.
5. Truncated/shouted/non-standard phrasing.
6. Accented speech — don't skip, known weak spot.
7. False-trigger check — background chatter that is not a call.

## 3. Metrics
Call-parse accuracy per condition, false-trigger rate, missed-call rate under overlap, end-to-end latency.

## 4. The interview narrative
Pick one specific failure Coval caught, show the condition, what broke, the fix, and the before/after metric.

## 5. Live-demo safety net
Every synthetic clip doubles as a "play a test scenario" option in the public demo UI.

## 6. Live-mic path status (fixed 2026-11-06)
Live-mic used to send browser SpeechRecognition transcripts straight to the backend — that never touched Deepgram, so it wasn't the thing being applied for. Fixed: browser MediaRecorder now streams raw webm/opus audio over the WebSocket as binary frames; the backend forwards it to Deepgram's live STT (`backend/app/deepgram_live.py`) and the resulting transcript runs through the identical `parse_call -> check_mismatch -> log` path the scenario fallback uses. Unverified end-to-end against a real `DEEPGRAM_API_KEY` as of this fix — only the degrade-gracefully-without-a-key branch has been exercised live.

## 7. Audio-level corpus + eval harness (built 2026-11-06)
Real audio now exists: `backend/audio_gen/generate_samples.py` generates 7 WAV clips into `audio-samples/` via macOS `say` + real numpy/soundfile signal mixing — genuine overlapping speech (TC2/TC3) and a genuine escalating white-noise bed (TC4), not just text fixtures. `audio-samples/manifest.json` holds each clip's ground truth.

`backend/eval/run_eval.py` runs that corpus through Deepgram's prerecorded STT (`backend/eval/deepgram_prerecorded.py`) and the SAME `parse_call`/`check_mismatch` code the live server uses, scores call-parse accuracy / false-trigger / missed-call / latency, and writes `audio-samples/scorecard.md`.

**The Coval gap, stated plainly:** this project's docs call for Pipecat → Coval integration specifically. Coval (coval.dev) is a third-party hosted product needing its own account/API key, which this build doesn't have — so it isn't wired in. What's built instead is a local, Deepgram-grounded harness covering the same test classes and metrics. If a `COVAL_API_KEY` shows up later, swap `transcribe_file` for Coval's ingestion API; the manifest/scoring logic doesn't need to change.

**Verified:** the scorer itself is unit-tested (`tests/test_eval_scoring.py`) to actually catch a misheard quantity and a false-trigger, not just pass cleanly — and `--mode mock` ran clean (trivially 100%, since it skips real STT) to prove the harness runs end to end. **Not verified:** real Deepgram transcription of the generated audio — needs `DEEPGRAM_API_KEY`, same gap as the live-mic path.

Accented-speech caveat (TC6): uses a different macOS `say` voice/locale (en_IN) as a stand-in for a real accent — a known limitation of synthetic TTS, not a substitute for real accented speakers.

## 8. Current status
`backend/tests/test_call_parser.py` and `backend/tests/test_mismatch.py` cover synthetic cases 1, 2, 5, 7 at the **transcript** level (text in, structured call out) — this is the logic Claude Code can verify without touching audio. `backend/tests/fixtures/transcripts.json` holds the corpus, reused by the parser tests now and by the demo's "play a test scenario" button once audio clips exist. Audio-level noise/overlap/Coval testing is not implemented yet (step 5 of CLAUDE.md's build order) — that requires real or synthesized audio files in `audio-samples/`, which don't exist yet.


---

## Original docs/FUTURE_IDEAS.md

# FUTURE_IDEAS.md

Brainstormed, not scoped, NOT implemented. Logged so the idea isn't lost — nothing here exists in code.

## Live kitchen-roll-call → online menu sync
Core idea: when the kitchen fires/86's an item (captured by the existing call-parser/mismatch pipeline), push that change out to a real-time online menu so it's visible outside the kitchen, not just logged internally.

Rough directions worth exploring later:
- **86-board sync**: when an item runs out mid-service (an "86 the duck" call), reflect that live on an online ordering page / QR-code menu, so customers don't order something that's already gone.
- **Prep/pace signal**: expose a lightweight "items fired in the last N minutes" feed — could inform a host stand or a waitlist app about kitchen pace, not just raw calls.
- **Front-of-house heads-up**: a non-blocking notification to servers when a fired item doesn't match what's on a customer's ticket (the existing mismatch detector), closing the loop between kitchen and floor instead of just logging it.
- **Multi-kitchen/location rollup**: if this ever runs across more than one kitchen, an aggregated "what's running low across locations" view.

## Open questions to resolve before scoping any of this
- Is the "online menu" a real target system (Square, Toast, a custom site) or would this need to build one from scratch? Changes the whole scope.
- Real-time push mechanism — webhook out from the FastAPI backend, or does the menu system poll?
- Does this stay back-of-house-only (PROJECT_SPEC.md's current non-goal boundary around front-of-house/customer-facing features), or does it deliberately cross that line? Worth deciding explicitly rather than drifting into it.

## Async kitchen-to-server comms / "heard" paging system
Core idea: a second, two-way channel distinct from fire-call capture. Servers get kitchen state (queue position, backed-up orders, item-ready pages) asynchronously - via a mic at a station they walk up to and trigger themselves, or an earpiece/phone feed - and pull messages on their own downtime rather than being interrupted mid-table. Includes a lightweight "heard" acknowledgment so a page is marked handled without needing a full reply.

Deliberately asynchronous by design: the explicit goal is to NOT erode the social/table-side interaction servers are mid-task on. This is the opposite direction of the current pipeline (kitchen voice -> structured log); this would be kitchen state -> server, pulled on demand.

Open questions before this gets scoped:
- This is kitchen-to-FLOOR-STAFF comms, not customer ordering, so it doesn't trip the "no customer-facing ordering" non-goal literally - but it's a second, much larger product (two-way dispatch/paging) layered on top of the current one (one-directional call capture). Worth deciding explicitly whether this becomes v2 of kitchen-copilot or a separate project, rather than drifting into it.
- Where does the "heard" ack get stored/surfaced - same structured log as fire calls, or a separate message queue entity?
- Earpiece/phone delivery implies a whole notification-delivery mechanism (push, SMS, a companion app) that doesn't exist anywhere in the current scaffold.

## Why this is a note, not a build
PROJECT_SPEC.md's whole discipline is "ship one scoped thing end-to-end, resist scope creep." This is exactly the kind of idea that's worth capturing before it's forgotten, but wrong to start building before the current scope (noise-robustness, Coval/eval, live-mic verification) is actually finished and demoable.
