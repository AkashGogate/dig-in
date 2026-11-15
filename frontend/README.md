# Operator frontend

The default [workbench](index.html) retains menu PDF/photo extraction, reviewed encoding/activation, bounded deliberate live voice, editable draft review, physical-zone recovery, and explicit print/speech summaries. Three additional operator screens integrate the teammate UI branch with the same `/api/v2` backend:

| Screen | Current behavior |
| --- | --- |
| [New order](server-order.html) | Select an existing saved draft or start one at a configured table; use its pinned menu; add/edit quantities, seats, canonical modifiers and guest requests; save, review and separately Confirm the current revision. |
| [My tables](server-tables.html) | View the selected server’s active tickets, pick up exact ready units, optionally close an entirely picked-up ticket as delivered, acknowledge/resolve structured kitchen updates, and explicitly ask for a displayed summary. |
| [Kitchen](kitchen.html) | Acknowledge submitted tickets; inspect per-unit station/seat/modifiers/guest requests; start units or manually verify ready plates; inspect actual physical zones and separate recipe/accepted-stock reference; send structured updates to the ticket’s owning server; explicitly ask for a displayed summary. |

Serve this directory on port 5173 with the backend on 8000 using the root README setup. `config.js` supplies the public HTTP origin. Hosted requests use same-origin `/api` rewrites. The static-site/backend access gate is separate from the simulated staff selection. When an API request actually returns 401, an explicit per-tab credential form appears and verifies access before reporting success. Credentials and staff sessions remain in memory; navigation asks for staff selection again, while saved orders remain in the backend. Cached browser Basic authentication works automatically where available.

Run checks with Node 22 after `npm ci --ignore-scripts`:

```sh
node --check data.js
node --check operator-pages.js
node --test tests/*.test.cjs tests/*.test.mjs
```

See [INTEGRATION](INTEGRATION.md) for extension seams and [UI_PLAN](UI_PLAN.md) for scope and unfinished work. Original incoming UI source is preserved as unloaded `.txt` reference under `prototypes/ui-abe9fb1/`; it is not an alternative runtime.
