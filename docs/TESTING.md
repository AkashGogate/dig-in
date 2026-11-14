# Testing and evidence

Current run results belong in [STATUS](STATUS.md), including environment gaps. Tests verify behavior at their actual layer; transcript checks and mock observations do not prove microphone quality, vision accuracy, hardware throughput, or production concurrency.

## Local checks

From `backend/`:

```bash
uv run pytest -q
uv run ruff check app/coordination scripts tests/test_coordination.py
uv run ruff format --check app/coordination scripts tests/test_coordination.py
# Fresh backend must already be running; this adds demo records:
uv run python -m scripts.smoke_demo
```

The heavier Pipecat pipeline is an optional extra (`uv sync --locked --extra live-pipeline`), outside the baseline checks. Default `uv sync --locked` should cover the server, tests, and direct Deepgram WebSocket/eval modules. If a full locked default install cannot be completed, use the exact verification environment documented in STATUS and state that limitation; do not silently treat a partial install as passing. Frontend is buildless; JavaScript syntax checks and browser smoke tests are appropriate, not an invented npm build. API schemas are available at `/api/v1/contracts` and `/openapi.json`.

## Coordination invariants

The automated domain/API checks should exercise these meaningful failures alongside successful transitions:

- Speech/model/observation cannot submit; manual human confirmation references the current reviewed draft revision. Corrections preserve unrelated lines, and stale revisions fail.
- A repeated dish/ambiguous read-back asks for seat/item clarification. The deterministic mock recognizes one quantity correction; it is not freeform speech understanding.
- Replayed stable IDs do not duplicate orders, tasks, observations, or accepted stock movements. An ID reused for different content must fail rather than mask new work.
- Submitted is not kitchen-acknowledged; acknowledged is not preparing. Partial plating does not make food ready. One ready dish does not make all dish units ready. Pickup is not served.
- Accepted inventory movement is separate from observation and recipe expectation; duplicate acceptance does not deduct twice. Returns/restock/waste/corrections preserve a reviewable reason/provenance.
- Full bays create waiting work, never overlapping assignments. Occupied/unresolved bays cannot be reused. Delayed events for an old assignment version fail.
- Two simultaneous claims yield one owner. Helpers are distinct additional staff slots; readiness requires ready food plus enough helpers. Release/block/cancel/complete follow validation.
- Missing positioning/speech/camera falls back to manual paths, with adapter state visible. Network failure is unsynced, not a fabricated successful order.

Use deterministic fixture IDs from `backend/app/coordination/fixtures.py`; tests should consume contracts rather than reproduce an alternative schema. Live-adapter changes require their own contract tests and regression scenarios.

## Browser/manual smoke

Use [DEMO_PLAN](DEMO_PLAN.md) with two browser sessions and a cook, one backend. Check a narrow phone viewport, keyboard navigation, long requests, empty queues, form labels, disabled/loading controls, invalid commands, and backend outage. Verify claims and updates appear in another tab/device. Browser UI checks complement API tests; they do not establish production authentication or real network persistence.

Record measured counts for duplicate effects, wrong table/ticket association, false ready, stock error and corrections, clarification/prompt count, claim conflicts, and ready-to-pickup delay. No benchmark values are claimed until measured. Record timestamps and fixture/scenario version when collecting them. Do not introduce staff performance/emotion surveillance.

## Preserved kitchen-call experiment

`backend/tests/test_call_parser.py`, `test_mismatch.py`, and `test_eval_scoring.py` cover transcript interpretation and evaluation scoring. `backend/tests/fixtures/transcripts.json` is reused by the original scenario fallback. `audio-samples/` already contains seven synthetic WAV clips and a manifest; earlier docs incorrectly said audio did not exist.

```bash
cd backend
uv run python -m eval.run_eval --mode mock
# Requires a Deepgram key and incurs provider usage:
# uv run python -m eval.run_eval --mode deepgram
```

Check the harness's `--help` before real usage; do not assume optional modes or provider availability. Mock mode proves harness plumbing and scorer execution, not transcription quality. The harness writes `audio-samples/scorecard.md`; preserve its provenance rather than silently treating regenerated mock scores as an improvement. Generating audio again with `audio_gen/generate_samples.py` uses macOS `say`, NumPy, and soundfile; checked-in fixtures allow other machines to run tests without macOS.

Synthetic conditions include clean, two overlapping stations, three simultaneous voices, escalating noise, truncated/shouted phrasing, a different TTS locale as an accent proxy, and background chatter. TTS accent variation is not a substitute for real diverse speakers. Real Deepgram microphone/prerecorded quality and noisy-room behavior need configured tests; no Coval connection is implemented. The retained legacy microphone has capped sessions and a scenario fallback; it does not submit Dig In structured orders.
