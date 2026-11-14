# Frontend lane

- `index.html`, `app.js`, `mvp.css` are the two-screen MVP (Server and Kitchen), using `/api/v2`. Read the root product/status/API docs and `backend/app/mvp/contracts.py` before changing payloads.
- `coordination-v1.html` / `coordination-v1.js` preserve the broader first scaffold against `/api/v1`; `legacy.html` preserves the earlier voice lab. Their states/contracts are separate. Do not put tasks, helpers, positioning, courses or shift navigation back into the default MVP.
- Keep manual entry and tap alternatives usable. Only human Confirm and send submits the current reviewed revision. Unknown terms/table mismatches stay visibly blocked until explicit review.
- Hold/release is currently a clearly labeled text-transcription simulator. Do not claim microphone capture, camera inference or live Databricks without verified adapters. Do not persist raw transcripts/audio or restaurant state in browser storage.
- Shared state, assignment versions, stable observations, deduplication and analytics semantics belong to the backend contracts. Retry the exact uncertain envelope, including ID/time; never fabricate success on outage.
- Maintain semantic labels, visible keyboard focus, 16px input text, phone reflow and honest empty/error/unknown states. Syntax-check all changed scripts (Node VM or `node --check`), inspect labels/IDs, and exercise the actual backend/browser path before claiming runtime verification.
