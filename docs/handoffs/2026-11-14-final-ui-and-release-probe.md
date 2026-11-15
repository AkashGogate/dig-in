# Latest UI integration and deployment probe correction

- Base: main `35d6d08` (merged PR #1); incoming UI `dd6886e`.
- Ownership: frontend agent owned presentation/theme/tests; Menu/Core owned the
  deployment probe, its tests, CI syntax entry and this handoff. Astra reviewed
  both bounded changes independently. No new provider calls were needed.
- Preserve the upstream commit as a merge ancestor and all nine incoming changed
  files byte-for-byte under `frontend/prototype-reference/ui-dd6886e/`.

## Implemented

Two Server screens now load a visible accessible light/dark control. Only the
theme preference is persisted, with invalid values, unavailable storage and
missing OS preference APIs handled. Kitchen remains forced dark. Canonical
client/session/commands and the full microphone/menu workbench are preserved.

Menu sections, descriptions, prices and selected quantities use the draft's
pinned canonical menu/category/item IDs. Imported categories remain visible;
changing menus clears a stale category filter. Missing prices stay unknown.
Upstream mock records/prices, fake feed state and alternate event bus remain
unloaded reference rather than operational state.

The read-only deployment probe previously accepted an older schema_version2
snapshot without menu_revision, then crashed comparing missing keys. It now
requires a nonempty string revision and validates voice-mode shapes before
membership checks. Old/malformed responses report failure without a traceback.
Seven focused regressions cover older/null/list state, valid current state,
required-live refusal and malformed/nested voice mode. CI syntax-checks theme.js.

## Verification and limits

- Frontend: 62/62 tests passed; Astra independently passed 32 operator/theme
  cases. Probe/auth: 13 passed; Astra independently passed all seven probe cases.
- Scoped lint/format and whitespace checks passed. No active backend order/voice
  authority or paid provider adapter changed in this follow-up.
- The final real Deepgram validation remains the four synthetic clips in
  [the preceding handoff](2026-11-14-final-deepgram-validation.md), including
  successful Server draft, Kitchen start/ack and one safe clarification.
- Root browser passed canonical sections/descriptions/unknown prices, a quantity2
  badge from two distinct draft lines, Save revision2 before enabling Confirm,
  dark theme persistence to My tables and return to light. No console errors
  appeared on the checked page. The new table-three test draft was saved but not
  submitted; seeded food milestones and the active menu were preserved.
- Hygiene passed300indexed paths; Gitleaks scanned46locally reachable commits
  with zero findings at the source checkpoint. Remote CI is checked before merge.

## Actual hosted release gap

Fresh post-PR1 read-only probe: frontend root/config return503, with public body
`Demo access is not configured.` Backend health remains404; state/OpenAPI and
frontend proxied state return200withoutlogin. Authenticated snapshots lack the
required menu_revision and fail the fixed probe. Proxied voice status returns200,
but that alone does not prove the full integrated release is deployed.

The signed-in deployment owner must set matching DEMO_AUTH_USER/PASS secrets on
Fly/Vercel, publish the reviewed root-context backend and verify hosted health,
login, proxy, direct WebSocket and upload flows. Keep auth fail-closed; do not
disable the gate to mask missing deployment configuration. Physical mic/CV,
phone/printer/earpiece and optional live semantic/Databricks remain unverified.

Untracked files with ` 2` suffixes appeared in the original local workspace from
an external operation. They were preserved, excluded from this isolated clone's
commits and not treated as reviewed teammate pushes.
