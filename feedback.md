
## Session 2026-11-06
- User wants plain/minimal tech choices when offered a choice, picked against the 4 core requirements (voice-native, technically impressive, live demoable, benefits people) rather than defaulting to the spec'd stack if it adds risk (chose plain HTML/JS frontend over Next.js to avoid npm/build risk for live demoability).
- User wants, at the end of a build session: (1) mapping of deliverable back to each stated requirement + a one-sentence description, (2) a resume-vault-formatted blurb for the project, (3) explicit call-out of any human input still needed, (4) env var / deployment shape summary. Proactively include all four without being re-asked each time.
- mcp__plugin_woz_code__Edit tool is unreliable in this environment — a hook mutates its input before the auto-mode classifier reviews it, causing repeated denial. Don't retry it more than once; fall back to Bash heredocs/python3 string-replace immediately.

## Session 2026-11-06 (cont.)
- User caught a real correctness bug via external review (live-mic was browser SpeechRecognition, not Deepgram, despite earlier claims it was voice-native/technically sound) — when told "check over this review," verify the specific technical claim being challenged against actual code before responding, and if the review is right, say so plainly and fix it, don't defend the original choice.
- User re-requests previous outputs tersely ("give me back the previous again", "wheres the vault notes?") — when that happens, regenerate the most recent matching artifact from this session's context (don't ask which one; the most recent version, updated for any fixes made since, is almost always what they want) rather than asking for clarification.
- mcp__plugin_woz_code__Edit's hook-rewrite-loop issue recurred again this session — confirms it's a persistent environment issue, not a one-off; keep defaulting to Bash/python3 string-replace for file edits for the rest of this project.

## Session 2026-11-06 (cont. 2)
- User runs git init/commits themselves mid-session without announcing it — when git history shows an unexpected commit, check `git log`/`git show --stat`/author before assuming the agent did something wrong; it turned out to be the user's own action (their own git author identity), not a bug or an unauthorized action by me.
- User's standing instruction this session: do not stage or commit anything, ever — only ever provide a commit message and let them run git themselves. Keep defaulting to this unless they explicitly say otherwise.
- When asked to "create a gitignore," check whether an adequate one already exists before writing a new one — in this case it already covered everything needed, so the right move was confirming that and explaining why, not fabricating unnecessary additions.

## Session 2026-11-06 (cont. 3)
- When a CI failure is reported with only a terse annotation (e.g. "exit code 2", no stdout), don't speculate from the error code alone — reproduce the exact CI environment (same OS/arch via Docker, same pip install list, same invocation command) before proposing a fix. Speculation here would have missed that the bug was invisible locally due to `python -m pytest` vs bare `pytest` sys.path differences.
- User's standing instruction holds across turns within a session without needing to re-state it: never stage/commit/push, only give commands or messages. Continued correctly this turn by handing back git commands instead of running them.

## Session 2026-11-06 (Claude Desktop gateway question)
- Note: this session's user turn was unrelated to KitchenNavigator code — a question about Claude Desktop's third-party inference gateway settings. Confirmed Gateway/Default settings route to pay-per-token API, not subscription auth; subscription login is a separate "Claude account" sign-in path, not a gateway URL. No code changes made.
- Recurring environment note (repeated again): Stop hook keeps requesting Skill(skill='caveman:compress'), which does not exist in the available skills list. Logged again for visibility — not actionable without a real skill of that name.

## Session 2026-11-06 (env vars, Coval decision, auto-mode prompting)
- User decided to skip Coval entirely due to cost - confirmed this is fine, not circular, since the eval harness scores against a hand-written manifest, not Deepgram's own output. Preference: keep using the local Deepgram-grounded harness as the permanent Coval substitute, not a stopgap.
- User reported auto mode still prompting despite being on - root cause: a PreToolUse hook in this project rewrites mcp__plugin_woz_code__Search/Edit inputs after the auto-mode classifier reviews them, invalidating the review. Noted as an environment quirk, not a Claude behavior issue - fall back to Bash for reads when this blocks file access repeatedly.
- Recurring environment note (repeated again): Stop hook keeps requesting Skill(skill='caveman:compress'), which does not exist. Logged again for visibility.

## Session 2026-11-06 (implementation status check)
- User asked a high-level "have we started implementation" question after a run of narrow technical Q&A - good practice confirmed: periodically give a full built-vs-remaining status summary rather than only answering the narrow question asked, since user is tracking overall project state across many short sessions.
- Recurring environment note (repeated again): Stop hook keeps requesting Skill(skill='caveman:compress'), which does not exist. Logged again for visibility.

## Session 2026-11-06 (spend discipline, real smoke test, scope flag)
- Strong, explicit preference confirmed: validate everything possible WITHOUT hitting a paid API first (mock mode, code review, logic checks); only spend on the API when nothing else proves it, and even then do the smallest possible real call (one clip, not the whole corpus) before scaling up. Apply this to all future Deepgram/Coval/any paid API work in this project.
- When the user floats a new feature idea that's actually a second product layered on current scope (not an extension of it), the correct move is: describe current scope honestly, name the idea as a separate thing, log it to FUTURE_IDEAS.md as a brainstorm, and explicitly ask the user to decide v2-vs-separate-project rather than silently building or silently dropping it. Confirmed this is the right call per CLAUDE.md's own "flag ambiguity back to Akash rather than guessing scope" instruction.
- Recurring environment note (repeated again): Stop hook keeps requesting Skill(skill='caveman:compress'), which does not exist. Logged again for visibility.

## Session 2026-11-13 9:56pm CST
- Recurring issue confirmed again: mcp__plugin_woz_code__Search/Edit calls get blocked by a PreToolUse hook that rewrites input after auto-mode classifier review, invalidating the review. Workaround: fall back to Bash cat/heredoc for reads/writes when this happens.
- caveman:compress skill does not exist (confirmed again across sessions) - Stop hook instruction to invoke it cannot be fulfilled.

## Session 2026-11-13 10:17pm CST
- User prefers Fly.io's GitHub-connected web UI deploy flow over local flyctl launch/deploy, even after local CLI was installed - don't assume CLI install implies CLI-driven deploy.
- Confirmed again: auto-stop/auto-start machines must be OFF on Fly for this project - persistent websocket audio connection is the whole reason Fly was chosen over Vercel; idle-sleep defeats that.

## Session 2026-11-13 10:43pm CST
- When user says "rate limit the API key" or "limit $ per request", verify what's actually achievable before implementing literally - Deepgram has no native per-request $ cap. Clarified prepaid-credit model as the real spend ceiling, then implemented the actual underlying ask (bot/abuse protection) as app-level rate limiting in code.
- User values verified claims over reassurance on security questions ("is it leakable?") - checked git history, grepped code paths, confirmed server-side-only key usage rather than just asserting it's safe.
- `python` / `python3 -m pytest` don't work in this repo's environment - must use `uv run pytest` from backend/.

## Session 2026-11-13 11:00pm CST
- Caught user about to deploy backend to Vercel (wrong root dir pointed at backend/ with FastAPI preset) - this directly violates CLAUDE.md's "no plain serverless/Vercel for agent runtime" constraint. Stay alert for this pattern: user juggling both Fly and Vercel UIs in parallel can mix up which repo folder goes where.

## Session 2026-11-13 11:21pm CST
- When walking user through unfamiliar hosting UIs (Vercel/Fly domain settings), explicitly warn before they touch an existing auto-generated entry - user was about to edit the default vercel.app domain instead of adding a new one.
- User is doing custom-domain setup (Squarespace DNS + Vercel + Fly) interactively, screenshot by screenshot - give one clear next action per message rather than the full multi-step plan every time.

## Session 2026-11-13 11:39pm CST
- Don't assume Vercel's generic cname.vercel-dns.com target is always correct for a custom domain - Vercel can assign a project/domain-specific CNAME target instead, shown under "DNS Change Recommended". Always read the live value off the user's own screen rather than reusing a generic value from memory.
- Squarespace's simplified DNS editor auto-appends the trailing FQDN dot - tell users to paste CNAME values without the trailing period Vercel's copy button includes.

## Session: repo migration to dig-in
- User wants repo migrated to github.com/AkashGogate/dig-in - confirmed via explicit choice: swap remote only, preserve full git history, NOT a fresh git init (destructive wipe was explicitly declined).
- Lesson: `git push` over https can hang silently with no output when it hits an interactive credential prompt and no TTY is available in this tool environment - don't wait indefinitely, kill it after a short timeout and hand the push back to the user to run from their own terminal, same pattern as the earlier blocked-push precedent this session (classifier blocked it there; here it just hangs on auth instead).

## Session: rebase-across-unrelated-histories recovery
- Lesson (hard-won, this session): when a `git remote set-url` points origin at a DIFFERENT pre-existing repo (not empty/fresh), never run `git pull --rebase` or `git rebase` against it without first checking `git merge-base <old> <new>`. If there's no common ancestor, rebase will either refuse or (worse) silently leave the branch pointer on the wrong commit and wipe the working tree down to just the other repo's files - looks like catastrophic data loss but commits usually survive via reflog/stash refs. Correct tool for combining two unrelated repos' histories is `git merge --allow-unrelated-histories`, not rebase.
- Preference confirmed: when something looks like a destructive git accident, diagnose fully (check reflog, stash, dangling commits, merge-base) and report exact recoverability BEFORE touching anything further - the dispatched fork agent did this correctly (did not blindly "fix" the wiped tree) and that was the right call; main thread then did the actual recovery with full context.
- Recurring environment issue, reconfirmed: `git push` to a remote repo hangs (not blocked by classifier this time, just hangs, likely waiting on a credential prompt with no TTY) when run via this tool - always hand pushes back to the user to run from their own terminal rather than waiting indefinitely.

## Session 2026-11-14 (deployment recovery, auto-mode / caveman confirmations)
- User asked to verify demo-credential gating before claiming the site is demoable, and explicitly wants to be told plainly if it's NOT accessible for any demo rather than a soft "mostly works" answer - confirmed good instinct: distinguish "properly locked behind working credentials" from "broken/offline returning a fail-closed error", these are not the same and must be reported as such.
- Before any live/production action (fly deploy, vercel login, setting prod secrets on Fly/Vercel), state the exact command list and wait for explicit go-ahead rather than proceeding - consistent with this project's standing rule on live/billable or production-affecting actions.
- Recurring environment issue, reconfirmed again: mcp__plugin_woz_code__Edit calls get invalidated by a PreToolUse hook that rewrites input after auto-mode classifier review (two consecutive denials this session). Fall back to Bash heredoc/python3 immediately after the first denial rather than retrying the same tool.
- caveman:compress skill still does not exist (confirmed again) - Stop hook's instruction to invoke it is not actionable.

## Session 2026-11-14 (Fly deploy recovery)
- Lesson: a Fly machine already in `stopped` state before `fly deploy` stays stopped after a rolling-strategy deploy — the deploy reconfigures it in place but does not start it, even with `min_machines_running = 1` in fly.toml. Must explicitly `flyctl machine start <id>` on each machine after deploying if they started out stopped. Check `flyctl status` after every deploy, don't assume a successful deploy means the app is reachable.
- Confirmed again: any Vercel/Fly CLI command needing interactive confirmation (vercel login, git push over https) hangs silently with no TTY in this tool environment - hand back to user immediately rather than waiting or retrying.

## Session 2026-11-14 (Vercel auth, local CLI vs tool shell mismatch)
- Lesson: `vercel login` run by the user in their own terminal does not carry over to this tool's shell - separate credential store/session. When CLI login is needed and the user says they've done it, verify with `vercel whoami` in this tool's own shell rather than trusting it transferred; if still logged out here, use the plugin:vercel:vercel MCP OAuth flow (authenticate -> send URL -> complete_authentication) instead of re-asking for CLI login.

## Session 2026-11-15 (Vercel fix landed, Fly suspension root cause)
- Lesson: when a hosting dashboard (Fly's GitHub integration) complains a config file is "not found" after a repo restructure, check two separate things before assuming the repo is wrong: (1) does the repo actually have the file at the expected path (it did - confirmed via `find`/`git ls-files` and a successful manual CLI deploy), and (2) does the dashboard integration have a stale remembered path setting from before the move. Diagnose both explicitly rather than guessing which one it is.
- Lesson: a Fly machine that starts fine and passes health checks can still be force-stopped minutes later by `flyd` itself if the app is suspended at the account/billing level (`flyctl apps list` shows this in the STATUS column) - this looks identical to an auto-stop/config issue from `flyctl status` alone; always check `flyctl apps list` STATUS when machines won't stay up despite correct auto_stop_machines=false config.

## Session 2026-11-15 (fly.toml location tradeoff)
- When user proposes reverting a teammate's structural change (moving fly.toml back into backend/) because it "seems smarter," check whether the change was load-bearing before agreeing or just doing it - here it was: the Dockerfile now COPYs files from outside backend/ (cv-service, schema dirs) because the backend gained a real cross-service dependency (CV event contract types for menu/CV integration). Explain the concrete breakage (Docker build context can't reach parent dirs) and offer the actual alternative (vendor the dependency) rather than silently complying or silently refusing.

## 2026-11-15 additional notes
- `caveman:compress` skill does not exist — confirmed again (this is now confirmed 9+ times this session alone). Stop-hook will keep demanding it; do not attempt it, no action needed beyond the HANDOFF/feedback writes.
- When asked "did we fix X and can we verify from here," re-check live state directly (flyctl/curl) rather than relying on session summary — state can have drifted (e.g. Fly suspension persisted, machines cycle stopped every ~5min) even within the same session's timeframe.
- `flyctl`/`fly` binary is not on PATH in this tool's shell — must call via full path `~/.fly/bin/flyctl`. Plain `flyctl`/`fly status` will fail with "command not found" here even though it works in the user's own terminal.

## 2026-11-15 additional notes (2)
- mcp__plugin_woz_code__Edit tool denied twice in a row this turn (PreToolUse hook rewrites input after classifier review, same recurring issue as earlier in session) — fell back to Bash heredoc immediately per existing standing workaround rather than retrying a third time.
- User pushed back on the billing-suspension diagnosis citing the Billing page showing "trial still active" — don't treat "trial active" and "has remaining credit/won't suspend" as the same claim; the $1 trial grant can be exhausted by 2 always-on machines within hours while the trial itself still shows as the active plan tier. Wait for user's screenshot before asserting further.

## 2026-11-16 additional notes
- Confirmed split-brain in-memory state bug live, not just theoretical: 2 Fly machines with no shared store round-robin requests, causing order data to appear/disappear between consecutive reads. `fly scale count 1` is the actual fix given current architecture (no Redis). Any future re-scale to >1 machine needs a shared store first, or every horizontal-scale test will quietly fail the same way.
- LineInput field gotcha for future test/demo scripting: `id` = the line's own identifier (any string), `menu_id` = the actual menu item reference (e.g. `gravel_pit_tots`). Easy to swap these by mistake — caused two failed test requests before realizing it.
- `flyctl apps list` STATUS column can show stale "suspended" for a bit even once billing is actually fine and machines run/pass health checks — don't over-trust that single field right after a billing fix; cross-check with actual machine state + live curl against `/healthz`.

## 2026-11-16 additional notes (UI pass)
- When a "theme"/"redesign" request can be satisfied with CSS alone (gradients/textures mimicking a material or mood), prefer that over sourcing/generating an actual image — avoids download-permission friction, copyright/sourcing questions, broken-asset risk, and extra page weight. Only reach for a real image if the user insists after seeing the CSS-only version.
- Before changing a shared CSS class's color/token, grep every HTML file for that class name first — `.eyebrow` and `.connection` are both reused on light backgrounds elsewhere in the same page; a global edit would have silently broken contrast in unrelated sections. Scope the override to the specific container instead.
- Claude in Chrome is turned off in this environment's settings — cannot visually verify UI changes in a real browser here; rely on full code read + ask user to click-test (consistent with the existing no-Playwright-testing rule, just for a different tool).
