# Local mock demo runbook

No credentials/hardware required for the coordination mock. Start the backend and static frontend using [README](../README.md). Use **one backend process** without reload and multiple tabs/devices; restarting resets coordination sessions/state. The [legacy mic/scenario experiment](http://localhost:5173/legacy.html) remains separately available, not the structured-order authority.

Fixture IDs/menu/options come from `backend/app/coordination/fixtures.py`: tables 1–3, salmon and risotto sharing greens, server-1/server-2/cook-1 plus lead-1, countable ingredient zones, bays A/B/C. Role session selection is simulated authentication. Use fresh command IDs for distinct operations and the same IDs for retry probes. API controls remain available at `/docs` for scenarios not yet exposed by role screens.

For a reproducible API-only smoke against a fresh backend, run `cd backend && uv run python -m scripts.smoke_demo`. Use `--base-url http://host:8000` for another demo host. It adds uniquely identified records, exercises two tickets, reviewed correction, duplicate retry, consume/return, partial plating, helpers, pickup, served and returned plate; it never resets others’ state. Existing occupied bays may prevent this scenario from fitting. Its timing is synthetic API timing, not a staff benchmark.

## Baseline sequence

1. Open a server session and tap Start order. Select table 1 manually or inspect the explicitly mock suggestion; correct it before proceeding. Keep table frozen unless deliberately edited. Add seat 1 salmon and seat 2 risotto, with configured modifiers and an explicit dietary request if useful.
2. Read back/type the mock phrase `seat 1 salmon quantity 2`. Inspect the proposed quantity diff: no silent overwrite and no send. Accept correction, review the revised full order, then tap **Confirm and send**. Spoken “yes” cannot send. A repeated menu item without a seat should ask which line to change; manual edit remains available.
3. In server-2's session, create another table's salmon order and send it. Confirm IDs/table/seat distinguish it from table 1's salmon.
4. In the kitchen, acknowledge by tap (voice is a future/live adapter seam). Confirm acknowledgment has not advanced dishes to preparing. Select the active prep ticket (`select_prep`) and advance the relevant dish units for prep. Explicitly supply order attribution on ingredient observations/movements; active context is not automatic ownership inference.
5. Inspect arrival-time bay assignment and table/course/batch labeling. Fill all three bays to exercise waiting-for-zone; do not assign overlapping dishes. Retain food/unresolved pickup until a verified pickup/release path clears the bay.
6. Emit a mock stable ingredient-zone change. Observe unresolved evidence before accepting a stock movement with quantity/reason/attribution. Repeat the same event/acceptance to check no duplicate deduction. Return a portion with a distinct movement; recipe expected usage must not double-deduct.
7. Emit plate-arrival evidence for one dish or advance a dish to partially plated. Confirm the ticket is not ready, contents/doneness are not claimed, and auto-ready is off. Cook explicitly marks the intended dish batch ready; a running task appears. Other queued/preparing units remain distinct.
8. Server-1 claims the run and requests one **additional** helper; server-2 joins its own slot. Verify food/helper blockers, claim visibility, and no double ownership. Exercise wait/split only through a supported command; do not claim an unfinished UI control exists.
9. Simulate an unambiguous pickup with current bay assignment version and claimed run. Ambiguous removal stays unresolved/asks for clarification. A cook/lead manually reconciles the current bay/version with occupancy and a reason; clearing food requires confirmed claimed pickup first. Explicitly confirm served in staff UI/API. A plate return is a distinct event, never a new order or stock decrement.
10. Show adapter status: unavailable speech, disconnected UNO Q, and mock cameras/positioning. Emit obstruction if supported and demonstrate manual fallback. Stop the backend temporarily: the client must show unsynced/error, never fabricated success; reconnect before further commands.

## API/invariant probes

Use `/api/v1/contracts` and `/docs` rather than inventing field names. Retries preserve the entire original envelope, including `occurred_at`, rather than regenerating a timestamp under the same ID. Automated tests in `backend/tests/` are the reproducible baseline for stale revision/assignment, command ID replay, atomic claim, ingredient duplicate, partial-vs-ready, and helper readiness cases. See [TESTING](TESTING.md). STATUS records which steps were actually exercised in browser/API tests; a runbook target is not itself evidence of completion.

Collect duplicate effects, wrong-table/ticket associations, false-ready events, stock error/corrections, prompt count, claim collisions, and ready-to-pickup delay. Start from a fresh backend for each comparable run. Report mock results as mock; no speech/CV/hardware benchmark is implied.
