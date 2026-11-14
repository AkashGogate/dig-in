# Testing and evidence

Use [STATUS](STATUS.md) for actual current results, [DEMO_PLAN](DEMO_PLAN.md) for the six beats and failure probes, and [analytics README](../analytics/README.md) for simulated data/SQL/metric limitations. Mock observations/transcripts do not measure CV/STT/hardware performance.

From `backend/`:

```bash
uv sync --locked --python 3.11
uv run pytest -q
uv run ruff check app/mvp app/analytics app/coordination scripts tests/test_mvp_*.py tests/test_coordination.py
uv run ruff format --check app/mvp app/analytics app/coordination scripts tests/test_mvp_*.py tests/test_coordination.py
# Start a fresh backend first; smoke adds uniquely identified demo records:
uv run python -m scripts.mvp_smoke --base-url http://127.0.0.1:8000
uv run python -m app.analytics.analyze fixtures/analytics/ten_scripted_orders.jsonl --summary
uv run python -m app.analytics.export fixtures/analytics/ten_scripted_orders.jsonl --simulate-failures 1 --attempts 3
```

No paid keys are required. CI runs the locked tests/scoped Python checks plus Node syntax checks; locally a Node VM/tool runtime may supply syntax validation if shell Node is unavailable. No separate static typechecker or frontend build is configured; runtime Pydantic schemas validate inputs/outputs. Full server startup/HTTP smoke complements route-isolated TestClient checks.

## Meaningful invariants

- Voice cannot send; current revision and explicit human Confirm tap required. Unknown/ambiguous menu terms and table mismatch block until explicit review. Edits do not erase flags silently. Correction count uses stable line baseline/final differences, not number of edit taps.
- Menu aliases/modifiers and nullable kitchen fields work for a second JSON menu without new hardcoded names. Unknowns/candidates never guess. Kitchen table/item utterances must not select the first same-table order or repeated unit.
- Submit/ack/start/ready/pickup/delivery are distinct. Quantity2 yields two physical dish units/zones. Acknowledgment reserves all K atomically or waits with none; concurrent orders cannot overbook. Release retries waiting orders; stale assignment versions fail.
- Stable no-hand ready-only occupancy/removal can drive default ready/pickup; hand/unstable/blocked/offline/unknown/empty-before-ready cannot silently complete/free. Unassigned/returned plates require review. Tap-ready/pickup works when camera blocked, without fabricating a start timestamp.
- Partial ready is not all-ready. Aggregate notification occurs once; duplicate event IDs do not repeat state/notification/export rows. Changed payload under the same ID fails.
- Recipe expectation and accepted observed stock stay separate; hand/change evidence alone does not deduct or imply progress.
- Analytics failure/slow drain does not block operations. Exact pending rows/time/ID survive retries within the process. Missing/uncompleted stages are null/censored; eligible manual/fallback denominator excludes mandatory Confirm and optional Delivered. Raw capture content cannot enter analytics.

## Browser and real rig limits

Exercise the default two-screen v2 against one shared backend with multiple actor sessions, long/empty/error/unknown states, explicit flag resolution, capacity, status and tap recovery. Verify phone reflow, keyboard/focus, labels,200%zoom and screen reader as available; record precise coverage rather than claiming broad accessibility. STATUS records the current Chrome path and explicitly untested checks.

Real STT requires deliberate capture/privacy review and noisy-room tests. The live Deepgram path (`backend/app/mvp/voice_live.py`) is unit-tested with a fake Deepgram (`tests/test_mvp_voice_live.py`, no key/cost); live runs are billable and need explicit approval per run, and so far cover synthetic `say` clips only; real CV requires calibrated overhead zones, stable interval/no-hand evidence, blocked/offline/returned plate scenarios and actual hardware timing. Cloud connector/SQL/dashboard work requires official capability verification and live workspace credentials. Synthetic fixture timings are not restaurant or staff benchmarks.

## Preserved regressions

The existing parser/mismatch/eval tests and broad `/api/v1` coordination tests remain regression coverage, not new MVP semantics. `scripts.smoke_demo` is v1 only. The original seven synthetic WAV clips/manifest and legacy eval remain available:

```bash
uv run python -m eval.run_eval --mode mock
# Real STT only with explicit provider configuration/usage:
# uv run python -m eval.run_eval --mode deepgram
```

Mock eval feeds ground-truth transcripts and proves scoring/plumbing, not microphone quality. The harness writes the checked-in scorecard; preserve provenance and do not claim regenerated mock scores as speech improvement. Legacy voice lab logging remains separate from v2 capture privacy. The optional Pipecat extra is outside the default checks.

## DIG IN voice eval (Coval-style harness)

`backend/eval/dig_in/` mirrors how [Coval](https://docs.coval.dev/concepts/simulations/overview) structures voice-agent tests, so the suite can move onto real Coval later without changing what it measures:

| Coval concept | Here | Notes |
| --- | --- | --- |
| Persona (how the caller sounds) | `personas.json` | `standard_server`, `rushed_server`, `line_cook_noise` (5 dB SNR), `interrupted` (overlapping second speaker), `accented`, `phone_quality` (8 kHz). Voice, rate, background, SNR, overlap, sample rate. |
| Test set (what they say + expected result) | `test_sets/*.json` | `server_orders` (8 cases: quantities, modifiers, mac-and-cheese "and", table mismatch, misheard name, seat + allergy, "no allergies", homophone table), `kitchen_callouts` (9 cases run end to end against seeded tickets), `safety_regressions` (7 real nova-3 transcripts from the first live run, fixed text, never billed). |
| Metrics (pass/fail) | `metrics.py` | `safety_outcome` exact / flagged / **wrong** (hard gate: 0 wrong), exact parse, table accuracy, item precision/recall, quantity, modifier, seat/dietary capture, flag correctness; live only: WER, STT latency, menu-term hit rate. |
| Run / simulation | `run.py`, `simulate.py` | A run = test sets x personas x mode with a fixed agent config (recorded in the run). Every persona gets the same cases, so differences come only from audio. Writes `runs/<run_id>.json` + `.md`; `--baseline` lists cases that got worse. |

Outcome meanings: **exact** = intended result; **flagged** = Confirm blocked or the cook asked to tap (safe, a human steps in); **wrong** = accepted silently with the wrong content, or the kitchen acknowledged/started the wrong ticket or dish. Kitchen cases seed real tickets in `Restaurant` and diff state, so `wrong` is a real wrong state change, not just a parse mismatch. The eval seeds tables 1-9; the demo fixture only configures tables 1-3.

From `backend/`:

```bash
uv run python -m eval.dig_in.run                                        # mock, free: scripted text through the real parser/domain + safety regressions
uv run python -m eval.dig_in.run --baseline eval/dig_in/runs/baseline-mock.json   # same, fail on any case that got worse
uv run python -m eval.dig_in.run --mode deepgram                         # renders audio (macOS say, free, cached), prints seconds/cost, REFUSES
uv run --env-file .env python -m eval.dig_in.run --mode deepgram --test-set server_orders --test-set kitchen_callouts --persona standard_server --confirm-billable
```

Mock mode is persona-independent (one `scripted_text` pseudo-persona) and proves plumbing and scoring, not speech accuracy. Deepgram mode uses the same params as the live mic adapter (nova-3, en, smart_format off, punctuate, `mip_opt_out`, menu keyterms) and refuses unless `--confirm-billable` is passed and the total audio is under `--max-audio-seconds` (default 120). **Run it only with explicit approval for that specific run.** Full matrix: 102 simulations, about 225 s of audio (about USD 0.029 at the 0.0077/min estimate; needs `--max-audio-seconds 240`). Generated audio lives in `audio-samples/dig-in/generated/` (gitignored, regenerable); routine run output in `eval/dig_in/runs/` is gitignored except the committed mock baseline and `20261114-first-live-deepgram.json` (first live run: 8 exact / 10 flagged / 0 wrong; rescored with the current parser: 10 / 8 / 0). The old `python -m eval.run_dig_in_eval` command still works. Synthetic TTS is not a real kitchen: only a recorded noisy-room run establishes real accuracy.

Moving to hosted Coval later: personas map to Coval personas (voice, background, interruption), each test-set case becomes a Coval test case (utterance + expected result), and `metrics.py` functions become custom metrics; keep the 0-wrong gate and the safety regressions as a deterministic transcript test set.
