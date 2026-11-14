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

Real STT requires deliberate capture/privacy review and noisy-room tests; real CV requires calibrated overhead zones, stable interval/no-hand evidence, blocked/offline/returned plate scenarios and actual hardware timing. Cloud connector/SQL/dashboard work requires official capability verification and live workspace credentials. Synthetic fixture timings are not restaurant or staff benchmarks.

## Preserved regressions

The existing parser/mismatch/eval tests and broad `/api/v1` coordination tests remain regression coverage, not new MVP semantics. `scripts.smoke_demo` is v1 only. The original seven synthetic WAV clips/manifest and legacy eval remain available:

```bash
uv run python -m eval.run_eval --mode mock
# Real STT only with explicit provider configuration/usage:
# uv run python -m eval.run_eval --mode deepgram
```

Mock eval feeds ground-truth transcripts and proves scoring/plumbing, not microphone quality. The harness writes the checked-in scorecard; preserve provenance and do not claim regenerated mock scores as speech improvement. Legacy voice lab logging remains separate from v2 capture privacy. The optional Pipecat extra is outside the default checks.
