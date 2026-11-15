# Final pull and completion audit

Menu/Core integration performed a fresh remote-head check after local acceptance.
The UI lane advanced through `21cc4a5` (Kitchen surfaces/grouped zones) and
`4d29098` (Server depth tokens). Voice `9fcdd95`, CV `7133aaf`, Menu/service
`9d3face` and main/menu base `c1d25fc` remained unchanged at that check.

The UI changes are integrated through merge ancestry, with canonical v2 behavior
retained and original prototype source kept as unloaded reference. No prototype
state writer, fabricated camera feed or automatic order action is enabled.

Source merge commits: `ba4e510` and `d6255be`. The final frontend suite passed
55/55 cases, including two added regressions for same-table ticket grouping,
retaining all physical zones despite station filtering, and review/mismatch
readiness guards. Astra independently passed 25 operator cases and cleared the
bounded source delta. Real local browser checks passed Kitchen tickets/grouped
zones, the eight-dish Server ordering menu, and My tables with the targeted
pickup update. Both checked pages had no console error entries. These checks
used existing shared state without changing food milestones.

The local scaffold scope is accounted for by
[INTEGRATION_ACCEPTANCE](../INTEGRATION_ACCEPTANCE.md). Independent Astra review
found no missing local scaffold requirement at the preceding `27a8619` checkpoint.
The [fresh acceptance pass](2026-11-14-end-to-end-demo-acceptance.md) covers 24
real HTTP checks and actual browser PDF correction/encoding/review/activation.

Repository hygiene passed for 283 indexed paths before this UI increment, and
Gitleaks scanned 42 locally reachable commits with zero findings. Local actual
environment files remained ignored and their values were not printed. CI on
`27a8619` passed all three jobs, including the 365 Python / 53 Node checkpoint
and container smoke; final UI checks are recorded in STATUS.

## Release is still separate

A fresh read-only hosted probe on 2026-11-14 America/Chicago still returned:

- Backend `/healthz`: 404; unauthenticated state/OpenAPI: 200.
- Frontend root/config: 200 without the expected login challenge.
- Frontend `/api/v2/state` and voice status: 404, including authenticated proxy.

These are outstanding release gaps, not a completed hosted deployment. The user
assigned publication to another signed-in agent. That owner must deploy this
integration branch, configure matching secrets, then rerun hosted/browser checks.
Physical CV/mic/phone/output, optional semantic provider and live Databricks
remain unverified. See [DEPLOYMENT_HANDOFF](../DEPLOYMENT_HANDOFF.md).
