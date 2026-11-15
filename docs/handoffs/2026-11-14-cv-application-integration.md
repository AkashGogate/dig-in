# CV application integration — 2026-11-14

- Owner/claim: CV branch application integration assigned by root, with Astra Max
  review of capture evidence, health/recovery and single-authority semantics.
- Branch/base: codex/cv-application-integration, isolated clone of the committed
  menu/service scaffold at9d3face; imported teammate origin/cv3b0d0a1 directories.
  No agent staging/commit/push. Root handles reviewed ancestry merges and deployment.
- Preserved teammate code: cv-service/, kitchen-backend/, schema/events.schema.json.
  The owning producer Pydantic events/schema are unchanged. Standalone kitchen
  service remains regression/reference code and is not active app authority.
- New canonical modules: backend/app/mvp/cv_bridge.py, cv_api.py and focused
  backend/tests/test_mvp_cv_bridge.py. Factory root splice is
  create_cv_router(lambda:mvp_api.restaurant), wrapped by app full-site auth.
  Docker packages owning cv-service/cvsvc/events.py at /app/cvsvc/events.py.
- Producer integration: new cvsvc/v2.py, config/v2.yaml, V2_INTEGRATION.md;
  minimal api/main/pipeline hooks attach actual per-frame counters/hand evidence.
  Default runner is manual mock, no cameras. Explicit --camera requires local
  hand model and matching human-calibrated empty references before feeds open.
  No first-frame-as-empty fallback in v2, raw/overlay MJPEG disabled, loopback bind.
- Safety semantics: measured monotonic >=1500ms stable dwell with max350ms frame
  gaps; real hand detector plus motion guard, conservative confidence>=0.7,
  capture-time zone/order/unit/version binding, one physical unit per zone. Counter
  retains multi-plate overflow rather than clamping2→1. Retry envelopes are frozen
  individually; one terminal stale rejection cannot erase peers. Bad health or
  recovery recount quarantines until explicit reconciliation/tap pickup recovery;
  occupied rebindings require stable empty before new ready. Watchdog uses Core
  status commands after10s; unknown never frees zones. Ingredient trip/count events
  require review and never trigger recipe/stock deduction.
- Privacy: incoming calibration PNGs were real camera photos, not synthetic test
  fixtures. Removed current-tip copies, added cv-service/.gitignore for local
  calibration PNGs; source history is preserved. Root must remove those tracked
  paths after actual CV merge. Tests use only synthetic generated frames/mock API;
  no live cameras, private frames, cloud providers or model downloads were used.
- Checks executed: locked CV environment47 tests passed (38 teammate +9 adapter/
  actual mock→canonical integration cases); locked standalone kitchen44 passed;
  canonical bridge12 focused cases and full backend147 passed with existing
  Starlette/httpx dependency warning. Scoped new-source Ruff lint/format passed.
  Actual ASGI loop covers CV mock plate→Core ready/pickup, and blocked→unseen
  removal→no auto pickup→explicit staff pickup→new assignment→stableempty→newready.
- Unverified: physical rig calibration/lighting, real MediaPipe model/hardware
  throughput/accuracy, private camera feeds and live deployment CV worker. CV
  transport is bounded in-memory; restart loses pending work. Full-site app auth
  is root-owned; local producer debug API must not be exposed publicly.
- Copy/integration notes: copy complete source CV/kitchen/schema dirs excluding
  environments/caches/logs/models/calibration captures; add the three canonical
  module/test files and this handoff. Avoid overwriting root server/auth/frontend
  work. No second Restaurant, no dual-write to standalone kitchen-backend. Root
  runs combined full-site/voice/CV/package checks and final authorized Git transfer.
