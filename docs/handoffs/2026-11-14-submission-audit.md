# Menu/Core pre-push audit

- Scope/authorization: user requested repository hygiene, secret/history and full
  task-scope audit, followed by commit/push if checks pass.
- Base: c1d25fc plus all prior uncommitted Menu/Core/service work; isolated audit
  clone and content-hash checks preserve concurrent edits.
- Cleanup: untrack .DS_Store without deleting the local file; expand root/Docker
  exclusions; add dependency-free indexed-file/example/ignore hygiene check to CI;
  correct three stale docs and env-template comments.
- Evidence: SUBMISSION_AUDIT lists scope acceptance, passing135 backend/21 UI
  behavior checks, source review, lint/format, dependency lock comparison and clean
  redacted Gitleaks current-tree/all-reachable-history scans.
- Publication: user-authorized task branch only; no main overwrite/force push,
  deployment, credential use for live providers or history rewrite.
- Limits: live provider/hardware/production limitations remain as documented; do
  not relabel mock adapters or global demo snapshots as production guarantees.
