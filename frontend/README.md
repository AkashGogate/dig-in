# Frontend — operator screens

Three back-of-house operator screens for the kitchen-copilot / dig-in system, plus
the original voice-pipeline demo page. Plain static HTML/CSS/JS — **no build step,
no framework, no dependencies**. Every screen talks to the kitchen through a single
data layer (`data.js`) that is mocked today and swaps to the real backend behind one
flag. See **[INTEGRATION.md](INTEGRATION.md)** for the data-layer contract and how to
wire the real backend.

> This directory is UI only. It does **not** change any `backend/` code.

---

## Screens & files

| File | What it is | Notes |
|------|-----------|-------|
| `server-order.html` | **Screen 1 — Take Order.** Server builds an order per seat; voice fills it in live. | iPad split view (menu / order); iPhone stacked with a menu sheet. |
| `server-tables.html` | **Screen 2 — My Tables.** Sidebar table list + floor map; tap a table for its dishes. | iPad sidebar+map; iPhone list-first with a **Map** button and a tab bar. |
| `kitchen.html` | **Screen 3 — Kitchen Display.** Ticket columns, zones grid, ingredients, last-heard strip. | **Always dark** (`<html class="force-dark">`). |
| `index.html` | Original voice-pipeline demo page (live-mic + test-scenario + log). | Pre-existing; not part of the three operator screens. |
| `data.js` | **The data layer.** Mock state, `api.*` methods, the event bus (`on`/`_emit`), and the `bus.*` appliers. One toggle (`USE_REAL_API`) flips mock → real. | Read [INTEGRATION.md](INTEGRATION.md) before wiring anything. |
| `server-alert.js` | Shared ready-for-pickup banner (chime + `navigator.vibrate` + Picked up). | Included on both server screens; listens for `server_alert`. |
| `style.css` | Apple-HIG design system: tokens, components, auto light/dark, `.force-dark`. | All visual styling lives here. |
| `config.js` | Sets `window.KITCHEN_COPILOT_API` (backend base URL). Defaults to `http://localhost:8000`. | |

---

## Running

These are static files — serve the `frontend/` directory with any static server:

```bash
cd frontend
python3 -m http.server 7788
# open http://localhost:7788/server-order.html
#      http://localhost:7788/server-tables.html
#      http://localhost:7788/kitchen.html
```

No `npm install` is required for the three operator screens (there is no `package.json`
here). To emulate the device sizes, use Chrome DevTools device mode:
**iPad** 1024×1366 · **iPhone** 390×844.

---

## Design system (`style.css`)

- **Typeface:** `-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif`.
- **Color:** Apple system colors as CSS custom properties (`--blue`, `--green`, `--orange`, `--red`, backgrounds, labels, fills). Light/dark switch automatically via `@media (prefers-color-scheme)`. The kitchen display is pinned dark with the `.force-dark` class.
- **Surfaces:** grouped inset lists, translucent blurred bars (`backdrop-filter`), bottom sheets, segmented controls. Touch targets ≥ 44px.
- **Icons:** inline SVG in the SF-Symbols idiom (no icon CDN — self-contained for demos).

### The one state rule (keep this everywhere)

> **Dashed blue outline = heard or seen but not yet confirmed.
> Solid fill with a green check = confirmed.**

This applies identically to: voice-added order items (Take Order), head-chef callouts
and camera clarification cards (Kitchen). The CSS hooks are `.unconfirmed` /
`.clarify-card` (dashed blue) and `.confirmed` / green accents.

---

## Voice & camera features (where each lives)

| Feature | Screen | Driven by event(s) |
|---------|--------|--------------------|
| Live transcript line + mic states (Listening/Paused/Processing/Offline) | Take Order | `voice_transcript`, `mic_status` |
| Voice-added items → **Accept** to confirm | Take Order | `voice_item`, `voice_item_accepted` |
| "Last heard" strip with **Undo** | Kitchen | `last_heard`, `last_heard_undo` |
| Camera / hand source icon on READY dishes | Kitchen | `dish_ready` (`dish.source`) |
| Camera status + **Mark ready** when offline | Kitchen | `camera_status`, `dish_update` |
| Clarification card ("Plate seen in Zone X, which dish?") | Kitchen | `clarification`, `clarification_resolved` |
| Ingredients: expected vs seen-leaving vs in-stock | Kitchen | `getIngredients()` |
| Ready-for-pickup banner (sound + vibration) | My Tables, Take Order | `server_alert` |

All of these are fed from `data.js` today. Nothing here calls the network while
`USE_REAL_API === false`.

---

## How a screen is wired (pattern)

Each screen:
1. Loads initial state with `await api.getX()`.
2. Renders from that state.
3. Subscribes to events with `on('event', cb)` and re-renders on change.
4. Sends user actions back through `api.*` (e.g. `api.markPickedUp(id)`), which
   mutates state and emits — so every open screen stays consistent.

There is **no per-screen networking code** — screens only know `api.*` and `on(...)`.
That is the seam an integration agent works behind. See **[INTEGRATION.md](INTEGRATION.md)**.
