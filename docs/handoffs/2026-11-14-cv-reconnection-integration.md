# CV reconnect increment integration

- Source: `origin/cv` `7133aaffeb8a59d7d588c69b75a48b1c29d6e300`, following already integrated `7e13c16`.
- Isolated clone: `/private/tmp/dig-in-cv-final-20261114`, branch `codex/cv-final-integration`, parent `94dda8964b19c8b8b2389487eff3da91dabab6d7`.
- Performed actual `--no-commit --no-ff` ancestry merge. No commit/push. Integration owner resolves/stages final source; isolated index retains merge conflicts until that step.

## Preserved team changes

Named macOS camera capture/reconnection in a spawned process, bounded backoff/grace period, CLI camera listing, legacy health debounce/adaptation, platform-marked PyObjC dependency/lock and incoming synthetic reliability tests are preserved. No independent kitchen-backend behavior is promoted to canonical authority.

## Canonical safety resolution

- Fixed calibrated health reference/background through startup and reconnect warmup; no rolling/statistic adaptation or auto-rebaseline. First degraded/moved-view qualified frame closes the gate. Warmup cannot contribute to readiness dwell.
- Resolve one unique named identity, retaining OpenCV AVFoundation's original sorted device indices; no missing/ambiguous name fallback. Config disallows named cameras outside the subprocess/numeric webcam path. Identity replacement after reconnect is withheld pending explicit restart/calibration review.
- Child JPEG envelopes retain sequence and capture-side wall/monotonic timestamps. Stale, repeated/reordered/future frames are withheld. Capture-time dwell and per-assignment/reconciliation time barriers prevent buffered old frames from acquiring new bindings. Changing reconciliation restarts the full dwell; identical context refreshes do not.
- Empty polls within350ms are permitted. Longer capture gaps/reopens immediately quarantine and restart warmup; staff recovery plus a new full dwell are required. Existing no-hand, confidence, overflow, circle agreement, current assignment/version, FIFO and single operational writer guards remain.
- Updated real `config/calibration/plating_cam.png` stays absent from the integrated tip and ignored locally. No private image was inspected, no camera opened, no model downloaded.

## Copy list for integration owner

Copy from this clone after performing the real merge in the integration clone:

```
cv-service/README.md
cv-service/V2_INTEGRATION.md
cv-service/config/cv.yaml
cv-service/config/v2.yaml
cv-service/cvsvc/config.py
cv-service/cvsvc/health.py
cv-service/cvsvc/main.py
cv-service/cvsvc/pipeline.py
cv-service/cvsvc/sources.py
cv-service/cvsvc/v2.py
cv-service/pyproject.toml
cv-service/tests/test_reliability.py
cv-service/tests/test_v2_circle_integration.py
cv-service/tests/test_v2_reconnection.py
cv-service/uv.lock
docs/handoffs/2026-11-14-cv-reconnection-integration.md
```

Resolve delete/modify calibration conflict by preserving deletion. No canonical backend, frontend, deployment or shared root docs are changed by this lane.

## Validation

- Locked dependency sync succeeded with Python3.11.18 in `cv-service/.venv` using the incoming lock. `uv lock --check --offline` passes. Exported requirements retain Darwin-only markers for all six PyObjC packages; this is a marker check, not execution on Linux.
- `.venv/bin/python -m pytest -q` in `cv-service`: **71 passed in28.28s**. Includes eight new canonical reconnect tests, incoming generated-video subprocess respawn tests, all native circle/legacy CV tests and mock API→canonical ready/pickup replay.
- Canonical backend: cached interpreter `python -m pytest tests/test_mvp_cv_bridge.py -q`: **12 passed**, one existing Starlette deprecation warning.
- Astra independently reran22 relevant v2 tests: **22 passed**, final source review cleared.
- Ruff check on changed config/health/sources/v2 and v2 tests passes; five formatted Python files pass format check. Existing broader legacy pipeline style was not rewritten.

Hardware accuracy, real sensor/driver acquisition timestamps, calibration geometry, hands model performance and production camera reconnection remain unvalidated. Software timestamps precede the capture read conservatively; they are not a claim of device-provided sensor timestamps. Live CV remains disabled until the physical rig is validated. No cloud or paid integration is enabled.
