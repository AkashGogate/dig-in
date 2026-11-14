# MVP six-beat demo and failure runbook

Start the one-worker backend/static frontend per [README](../README.md); use `/api/v2` and the default Server/Kitchen screens. Sessions and cameras are explicitly simulated. Fresh state avoids unrelated occupied zones; never reset others’ active demo. The [MVP API smoke](../backend/scripts/mvp_smoke.py) runs with `cd backend && uv run python -m scripts.mvp_smoke --base-url http://127.0.0.1:8000`; it adds demo records. The older smoke_demo is v1.

## Six beats

1. **Reviewed draft.** Select Server One/table1. Enter a two-item menu order manually, or hold/release the labeled transcript simulator with `Table 2: one salmon no butter and one risotto` using the starter menu. The spoken table differs: Confirm stays blocked. Explicitly choose selected/spoken table, review every menu/quantity/modifier/flag, then human **Confirm and send**. No actual microphone records in this simulator. Unknown dish terms require manual correction/explicit review, never a guessed dish.
2. **Acknowledge and reserve.** Kitchen device acknowledges by tap or mock `Heard, table 2` phrase. Two physical dish units get two distinct zones atomically. Quantity2 on one menu line also requires two zones. Table alone is not a unique order ID; same-table additions/identical dishes must clarify instead of selecting first.
3. **Start and timer.** Start a specific dish by tap or constrained mock `Start table 2 salmon` if unique. Show elapsed and known menu typical minutes, not percent cooked. A tap-ready without a recorded start must leave that start unknown.
4. **First plate/partial.** Simulate stable occupied evidence1500ms/no hand at the assigned zone/version. It marks that physical dish ready under the explicit finished-plates-only convention; show1of2, no all-ready notification yet. No food/doneness recognition is claimed.
5. **Blocked camera/tap recovery.** Mark plating camera blocked. It becomes unknown rather than empty/free. Cook taps Ready for the second dish after reviewing it. One all-ready notification appears. Restoring camera status alone must not invent empty zones; use fresh evidence or reviewed tap state.
6. **Pickup/export.** Stable empty after occupied evidence or explicit staff Pickup frees each physical zone and retries waiting work. After all picked up, optional Delivered closes the order. Inspect `/api/v2/events`, analytics health/pending or local JSONL export. The **SIMULATED** ten-order analyzer/SQL assets demonstrate timeline questions; no live Databricks dashboard is claimed.

## Failure probes

Use test fixtures/API docs for precise payloads, never invented field names. Try an unknown menu term/table mismatch, two open orders at one table, quantity>1 ambiguity, six full zones then another acknowledged order, concurrent allocation, stale assignment version, hand/short-stability signal, blocked removal, empty-before-ready, occupied unassigned zone, returned plate and duplicate retry. Uncertainty stays visible, stock/orders do not silently change, and manual taps/reconciliation recover without overbooking. A waiting order has automatic release retry and a kitchen retry action.

Stop/disable analytics or simulate failures: operational actions continue while pending exact rows/attempts/error health remain visible. Duplicate IDs do not add sink rows. Stop the backend: UI must say unsynced and preserve uncertainty, not claim offline success. Retry the exact envelope including ID/time after reconnect.

Ingredient evidence is secondary: simulate countable stable change, inspect unresolved observation, accept one movement with reason, replay without another deduction, return/correct separately. Recipe expectation is not another deduction. The second JSON menu proves no new hardcoded names; unknown imported kitchen data stays null.

Record stage counts/censored stages, correction counts/denominators, eligible manual/fallback share, zone wait, camera blocked/offline/unexpected counts, duplicate/wrong-ticket/false-ready/stock effects and synthetic timing separately from real rig timing. Every simulated result/tile says SIMULATED and includes sample count/run ID. The current exact executed subset is in [STATUS](STATUS.md); a runbook is not evidence all probes ran manually.
