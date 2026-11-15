# Incremental CV integration — 2026-11-14

- Owner/claim: root-assigned incremental CV lane, supervised by Astra Max. Isolated
  clone branch codex/cv-increment-integration from application integration d5646f5.
- Incoming ancestry: origin/cv7e13c162cd313844d6079f39fac7f191410ca5d0 over3b0d0a1.
  Performed a real no-commit/no-ff ancestry merge. Only pipeline.py conflicted;
  source is resolved and tested; index deliberately remains unmerged for root's
  actual merge/copy/review. No child commit or push was performed; merge preparation alone populated the isolated index.
- Preserved additions: shape-based circle detector, optional config, upstream
  synthetic circle tests and standalone kitchen active-ticket advancement/tests.
- Canonical safety: merged same-frame circle counts with existing actual hand and
  measured sampler. Canonical circles require agreement with calibrated per-bay
  counter and preserve its confidence; disagreement/low confidence withholds both
  readiness and empty/pickup. Circle footprint boundary/neighbor/gap ambiguity
  withholds all touched zones. Overflow cannot be clamped into one valid unit.
  Default v2 detector stays bays; new static-scene health autorebaseline is disabled
  specifically in canonical v2 while original legacy behavior remains available.
- Legacy boundary: active-ticket advancement remains solely in preserved standalone
  kitchen-backend. No canonical queued order auto-start, recipe deduction or second
  application authority is introduced. All prior hand/reference/max-frame-gap/
  confidence/version/quarantine/explicit recovery guards are preserved.
- Checks: incoming circle tests plus five narrow canonical integration cases pass;
  full CV suite55passed, standalone kitchen49passed, canonical bridge12passed.
  Existing dependency deprecation warning remains. New test/v2 module scoped Ruff
  lint/format and source compilation pass. No live camera/model/cloud calls.
- Root copy set: cv-service/config/{cv.yaml,v2.yaml}; cvsvc/{config.py,health.py,
  pipeline.py,v2.py}; cvsvc/plating/circles.py; tests/{test_circles.py,
  test_v2_circle_integration.py}; V2_INTEGRATION.md; kitchen-backend/kbackend/
  {config.py,service.py}; tests/test_active_advance.py; this handoff. Root owns
  actual merge commit, combined application verification, CI and authorized push.
- Limits: synthetic shape success does not establish hardware/noisy-room/lighting/
  geometry accuracy. Optional circles stays calibration-dependent. No new private
  captures, raw frame fixtures, credentials or model downloads were introduced.
