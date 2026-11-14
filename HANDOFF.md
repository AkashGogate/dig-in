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
