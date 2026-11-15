# Testing and evidence

Use [STATUS](STATUS.md) for actual current results, [DEMO_PLAN](DEMO_PLAN.md) for the six beats and failure probes, and [analytics README](../analytics/README.md) for simulated data/SQL/metric limitations. Mock observations/transcripts do not measure CV/STT/hardware performance.

From `backend/`:

```bash
uv sync --locked --python 3.11
uv run python -m scripts.check_repository_hygiene
uv run pytest -q
# Role routing, update lifecycle, canonical lineup and read-only summaries:
uv run pytest -q tests/test_mvp_service.py
# Focused mutable-menu integration tests:
uv run pytest -q tests/test_mvp_menu_runtime.py
# Encode the artwork menu offline into new ignored output paths:
uv run python -m scripts.menu_tool fixtures/menus/dig-in.json --output outputs/menu-review.json
uv run ruff check app/mvp app/analytics app/coordination scripts tests/test_mvp_*.py tests/test_coordination.py
uv run ruff format --check app/mvp app/analytics app/coordination scripts tests/test_mvp_*.py tests/test_coordination.py
# Start a fresh backend first; smoke adds uniquely identified demo records:
uv run python -m scripts.mvp_smoke --base-url http://127.0.0.1:8000
uv run python -m app.analytics.analyze fixtures/analytics/ten_scripted_orders.jsonl --summary
uv run python -m app.analytics.export fixtures/analytics/ten_scripted_orders.jsonl --simulate-failures 1 --attempts 3
```

No paid keys are required. CI runs the locked tests/scoped Python checks plus Node syntax checks; locally a Node VM/tool runtime may supply syntax validation if shell Node is unavailable. The dependency-free frontend suite runs with `npm ci --ignore-scripts --prefix frontend` then `node --test frontend/tests/*.test.cjs frontend/tests/*.test.mjs` from the repository root and is included in CI. No separate static typechecker or frontend build is configured; runtime Pydantic schemas validate inputs/outputs. Full server startup/HTTP smoke complements route-isolated TestClient checks.

## Meaningful invariants

- Voice cannot send; current revision and explicit human Confirm tap required. Unknown/ambiguous menu terms and table mismatch block until explicit review. Edits do not erase flags silently. Correction count uses stable line baseline/final differences, not number of edit taps.
- Menu changes prepare/encode outside the operational lock, require lead/tap review and current menu revision, and preserve old drafts/ticket labels/kitchen speech/recipe interpretation. Invalid vectors or enqueue failure cannot replace the active menu. Default vectors are lexical; mocked remote tests do not establish semantic quality.
- Menu aliases/modifiers and nullable kitchen fields work for a second JSON menu without new hardcoded names. Unknowns/candidates never guess. Kitchen table/item utterances must not select the first same-table order or repeated unit.
- Submit/ack/start/ready/pickup/delivery are distinct. Quantity2 yields two physical dish units/zones. Acknowledgment reserves all K atomically or waits with none; concurrent orders cannot overbook. Release retries waiting orders; stale assignment versions fail.
- Stable no-hand ready-only occupancy/removal can drive default ready/pickup; hand/unstable/blocked/offline/unknown/empty-before-ready cannot silently complete/free. Unassigned/returned plates require review. Tap-ready/pickup works when camera blocked, without fabricating a start timestamp.
- Partial ready is not all-ready. Aggregate notification occurs once; duplicate event IDs do not repeat state/notification/export rows. Changed payload under the same ID fails.
- Recipe expectation and accepted observed stock stay separate; hand/change evidence alone does not deduct or imply progress.
- Analytics failure/slow drain does not block operations. Exact pending rows/time/ID survive retries within the process. Missing/uncompleted stages are null/censored; eligible manual/fallback denominator excludes mandatory Confirm and optional Delivered. Raw capture content cannot enter analytics.

## Service coordination acceptance

Use Server One/Server Two and Kitchen sessions on one backend. Submit a quantity2
order as Server One; acknowledge as Kitchen (no start implied), start one unit,
mark only that plate ready, and publish pickup coordination. Server Two has no
addressed update. Server One acknowledges the message without changing food,
picks up the one ready unit, and refreshes the summary: current-ready becomes0,
cumulative-ready stays1/2, and the historical pickup request is non-actionable.
Resolve the message independently. Summary reads must not mutate events/orders.

UI behavior tests cover explicit summary reads, fake Print/Speak/Stop, cancellation
on state/session/view/outage, stale playback blocking, unsupported speech, escaped
notes, waiting-zone start, unit distinctions, timer advancement and focus retention.
Fakes do not verify audible output, earpiece routing or physical printers.

## Browser and real rig limits

Exercise the default service screens and secondary Menu setup against one shared backend with multiple actor sessions, long/empty/error/unknown states, explicit flag resolution, capacity, status and tap recovery. Verify phone reflow, keyboard/focus, labels,200%zoom and screen reader as available; record precise coverage rather than claiming broad accessibility. STATUS records the current Chrome path and explicitly untested checks.

Real STT requires deliberate capture/privacy review and noisy-room tests. The live Deepgram path (`backend/app/mvp/voice_live.py`) is unit-tested with a fake Deepgram (`tests/test_mvp_voice_live.py`, no key/cost); live runs are billable, require configured provider access and deliberate authorization, and the inherited scorecard covers synthetic `say` clips only; real CV requires calibrated overhead zones, stable interval/no-hand evidence, blocked/offline/returned plate scenarios and actual hardware timing. Cloud connector/SQL/dashboard work requires official capability verification and live workspace credentials. Synthetic fixture timings are not restaurant or staff benchmarks.

## Preserved regressions

The existing parser/mismatch/eval tests and broad `/api/v1` coordination tests remain regression coverage, not new MVP semantics. `scripts.smoke_demo` is v1 only. The original seven synthetic WAV clips/manifest and legacy eval remain available:

```bash
uv run python -m eval.run_eval --mode mock
# Real STT only with explicit provider configuration/usage:
# uv run python -m eval.run_eval --mode deepgram
```

Mock eval feeds ground-truth transcripts and proves scoring/plumbing, not microphone quality. The harness writes the checked-in scorecard; preserve provenance and do not claim regenerated mock scores as speech improvement. Legacy voice lab logging remains separate from v2 capture privacy. The optional Pipecat extra is outside the default checks.

## DIG IN voice eval

Server orders and Kitchen callouts, each clean / kitchen noise bed / overlapping second speaker (18 synthetic `say` clips, 52s, `audio-samples/dig-in/`). From `backend/`:

```bash
uv run python -m eval.dig_in.run --mode mock
# Free exact-duration preflight; audio rendering uses macOS say:
uv run python -m eval.dig_in.run --mode deepgram --max-audio-seconds 600
# After deliberate authorization, add --confirm-billable and configure the key.
# Narrow with --test-set server_orders --persona standard_server if needed.
```

Live scoring uses the same nova-3/keyterm/`mip_opt_out` params as the live adapter. Run it only within explicit live-testing authorization, then add `--confirm-billable` (needs `DEEPGRAM_API_KEY`). The scorecard (`audio-samples/dig-in/scorecard.md`) states its mode; synthetic TTS is not a real kitchen.


## Combined application and deployment checks

Use separate locked environments; running pytest from the repository root mixes
three different applications and import paths. From each of backend/, cv-service/
and kitchen-backend/: `uv sync --locked --python 3.11`, then `uv run pytest -q`.
The independent kitchen suite is legacy regression coverage, not active app state.
Backend composition tests exercise the real app routers/middleware/lifespan,
menu activation and old drafts, voice review, producer schema, recipient summaries
and legacy paid-audio refusal. CV tests include actual synthetic pixel counting,
replay and producer mock→canonical Core integration; no private frames/models/rig.

Frontend requires Node22 and its pinned middleware dependency:
`npm ci --ignore-scripts --prefix frontend`, then
`node --test frontend/tests/*.test.cjs frontend/tests/*.test.mjs`.
Check all frontend .js syntax, including voice-audio.js. CI additionally builds the
root Docker image and verifies canonical app/CV contract imports; it does not
publish the image or call providers. No broad cross-browser/physical device claim.

`uv run python -m scripts.smoke_deployment` is a read-only hosted release check.
Credentials come from environment only. `scripts.mvp_smoke` also accepts those
environment values, but creates labeled simulated orders and needs a fresh menu
with at least two dishes/free zones. See DEPLOYMENT for real hosted browser,
large PDF/photo proxy uploads, paced synthetic STT and physical rig checks.


The current voice harness uses test sets × six synthetic personas; MOCK collapses
scripted persona duplicates and includes fixed historical failure transcripts.
Current test sets use canonical menu IDs. Historical run artifacts are preserved
unchanged and labeled in eval/dig_in/runs/README.md. Generated audio and routine
reports stay ignored. Empty/nonfinite clips fail before provider calls. Exact
sample durations enforce a finite positive cap; only display is rounded.
Live evaluation propagates the shared minimum finalized-word confidence through
live domain commands. Any missing/invalid segment metadata remains unknown.
Low/unknown live speech blocks Server send for explicit full-draft review and
makes Kitchen clarify; mock text with no confidence stays usable. The0.6 threshold
is provisional, not calibrated accuracy. Unit scoring retains duplicate physical
units; a passed safety gate can include safely flagged, inaccurate transcripts.
