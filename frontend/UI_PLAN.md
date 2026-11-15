# UI plan & design handoff

For whoever picks up the frontend next. This is the **why** behind the three
operator screens and the design direction — read it with [README.md](README.md)
(per-file map) and [INTEGRATION.md](INTEGRATION.md) (data/backend contract).

---

## Goal

Back-of-house coordination for a voice-native kitchen. Three operator screens, built
to feel like a **native Apple app**: modern, minimal, content-first, and legible at a
glance in a busy service. Plain static HTML/CSS/JS — no framework, no build step.

Design north star: Apple Human Interface Guidelines — clarity, deference (content over
chrome), and restraint. If a screen looks "designed," it's doing too much.

---

## Design principles (hold the line on these)

1. **Color means status, nothing else.** Green = ready, orange = cooking, blue =
   sent / informational / unconfirmed-voice, red = alert/allergy. Everything else is
   neutral grays. No decorative color, no gradients, no rainbow accents.
2. **One state-visual rule, everywhere:** dashed blue outline = *heard or seen but not
   confirmed*; solid fill + green = *confirmed*. Applies to voice-added order items,
   head-chef callouts, and camera clarification cards.
3. **Content first.** Generous whitespace, hairline separators over boxes, restrained
   shadows (surfaces separate by tone, not float). Let type hierarchy do the work.
4. **Real icons, never emoji.** Inline SF-Symbols-style line SVGs. (Emoji is the
   fastest way to make this look AI-generated — don't reintroduce it.)
5. **Native components.** Grouped inset lists, segmented controls, bottom sheets,
   translucent blurred bars, ≥44px touch targets.
6. **Light/dark auto** on server screens via `prefers-color-scheme`; the kitchen
   display is pinned dark (`.force-dark`) because it lives on a wall in a bright room.

All tokens and components live in `style.css` (`:root` custom properties + `.force-dark`).

---

## The three screens

### 1. Take Order — `server-order.html` (iPad split / iPhone stacked)
- **Left:** menu. Search, a quiet **text category filter** (not icon tiles), and a grid
  of calm item cards (name + price, no icon). Cards stay neutral until added, then take
  a subtle blue tint + count badge.
- **Right:** the order as grouped inset lists per seat. Voice banner + live transcript
  line; mic states Listening / Paused / Processing / Offline. Allergy as a red capsule.
  Delivery segmented control. One primary blue "Confirm and send to kitchen".
- Voice-added items appear **dashed-blue with Accept**; Accept turns them solid.
- iPhone: menu becomes a bottom sheet (FAB); Prev/Next seat nav.

### 2. My Tables — `server-tables.html` (iPad sidebar+map / iPhone list-first)
- **Sidebar:** "My tables" / "Other tables" inset lists — colored number chip, dish
  summary, status, time.
- **Floor map:** large "Floor" title, section segmented control, tables as **quiet
  surface tiles** — number + one short status line, soft status tint, dashed "ghost"
  tiles when empty, a gentle pulse when ready. (Deliberately *not* saturated blobs.)
- Tap a table → bottom sheet with dishes, zone labels, Picked up / Mark served.
- **Ready-for-pickup alert** banner (sound + vibration + Picked up) via `server-alert.js`.
- iPhone: list first with a **Map** button and a line-icon tab bar.

### 3. Kitchen Display — `kitchen.html` (always dark)
- Translucent top bar: **Tickets | Zones | Ingredients** segmented control, mic +
  camera status indicators, station filter, all-day dish summary.
- **Last-heard strip:** each voice command → result, with a big Undo, readable across
  the room.
- **Tickets:** columns oldest-left, timers warming orange→red, dishes grouped by seat,
  allergies as red capsules, camera/hand icon on READY dishes, Mark-ready when the
  camera is offline.
- Head-chef callouts and camera clarification cards render **dashed blue** until
  confirmed; confirmed tickets get a solid green top accent.
- **Zones** grid and **Ingredients** (expected vs seen-leaving vs in-stock) views.

---

## What the last pass changed (minimalist redesign)

Moved it from a generic "dashboard" look to the Apple direction above:
- Removed **all emoji** (category tiles, tab bar, delivery chips) → text / line icons.
- Dropped the **rainbow colored-initial circles** on menu items → calm name+price cards.
- Floor tables: **saturated blobs with 4 cramped lines → quiet tiles**, number + one
  status line, soft tint, dashed empties.
- Softer shadows, tighter large-title tracking, consistent radii/spacing.

---

## Conventions for the next person

- Edit shared look in `style.css`; keep per-screen `<style>` blocks to layout only.
- Add status meaning with the existing color tokens — don't invent new accent colors.
- New icons: inline SVG, 1.7–2px stroke, `currentColor`. No icon CDN (keep it
  self-contained for offline demos).
- Keep the dashed-blue / solid-green rule intact — it's load-bearing for the product.

## Open / future UI items

- True iPhone QA in a real narrow viewport (the embedded dev browser is locked to a
  wide width; verify in Chrome DevTools device mode 390×844).
- Server-screen light-mode default (currently follows system) if that's desired for the
  floor hardware.
- Empty/loading/error states for when real data is wired (see INTEGRATION.md).
- Accessibility pass: focus rings, VoiceOver labels on icon-only buttons.
