
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
