# Menu/Core submission audit — 2026-11-14

This audit covers the current menu and integration task, including both user
flows. It is a credential-free scaffold submission, not a production-readiness
or live-provider/hardware certification.

## Scope acceptance

| Requested aspect | Implemented and checked |
| --- | --- |
| Mutable menu input | JSON/CSV/TXT normalization, deterministic IDs, canonical item/modifier aliases, null unknown kitchen fields |
| PDF/photo input | Local PDF/PNG/JPEG OCR, editable provisional dishes, add/remove/correct controls, source evidence, then canonical preparation |
| Automatic encoding | Local lexical vectors; replaceable provider with mocked semantic adapter; candidate-only matching, never implicit send |
| Review and activation | Lead/tap review, expected active revision, atomic menu/index selection + event/outbox, exact retry and old-draft/ticket pinning |
| Server journey | Reviewed ordering/table/unknown gates, current-revision Confirm, kitchen updates, explicit coordination handling and requested summaries |
| Kitchen journey | Canonical physical-unit lineup with context/timers, ack/start/ready/pickup separation, zones/FIFO/version guards and targeted staff updates |
| Connection and outputs | Recipient/role-scoped summaries and update commands, current-ready vs historical-ready, explicit display/Print/Speak/Stop and stale cancellation |
| Agent/teammate integration | Focused modules, source-owned contracts, INDEX/task map/integration guide, complete flow documentation and unique lane/root handoffs |
| Existing work preservation | Legacy/v1/parser/eval and labeled synthetic fixtures retained; no wholesale replacement or automatic migration |

Independent Astra Max source/contract review found no remaining submission blocker.
Three documentation mismatches (OCR status, frontend suite command and current
handoff link) were corrected. The 37 installed cached test dependencies
checked against the lockfile matched their locked versions.

## Executed checks

- 135 backend tests passed, including menu/runtime/extraction/service regressions.
- 21 frontend behavior cases passed in native Node VM (9 menu + 12 service), plus
  all configured app/module script syntax checks. CI runs these with Node's test
  runner; this local environment has no standalone Node command.
- Scoped Ruff lint/format and Git whitespace checks passed. New hygiene checker
  verifies indexed filenames, blank credential examples and representative ignore
  rules. HTML assets/unique IDs/labels and documentation references were reviewed.
- Existing real HTTP MVP smoke and combined two-role browser/HTTP acceptance passed
  in the preceding implementation checkpoint; no product code changed in this
  submission audit. See STATUS and the service/menu handoffs for exact coverage.
- Gitleaks 8.30.1 (official release archive checksum verified) returned zero findings
  on the candidate source directory and all locally reachable Git history, with
  redacted reports kept outside the repository. Scans do not prove every possible
  credential is detectable; keep secret values outside version control.

## Repository hygiene and intended content

The previously tracked .DS_Store is removed from the index while its local file is
preserved. Root ignores cover real env files, virtual environments, caches,
credential/key material, runtime databases/logs, exports and recordings. Docker
context exclusions also cover envs, caches, keys, runtime DBs and generated output.
CI now runs scripts.check_repository_hygiene to prevent recurrence.

Only blank .env.example credential fields are intentional templates. The eight-dish
menu image/prompt, synthetic WAV clips and labeled analytics JSONL fixture are
portable demo assets, not private capture exports. No new provider credential,
local environment, database, capture, cache, tool download or scan report belongs
in this commit. No history rewrite/force push is part of this audit; removing
.DS_Store from the current tree does not erase previously published history.

## Honest remaining limits

Local hashing is not trained semantic accuracy. Live semantic/STT/CV/Databricks,
Linux/container OCR execution, physical printing, audible/headphone output,
production auth/confidential state delivery, persistence and distributed workers
remain unverified/separate work. Structured summaries/handling are scoped, but
global demo snapshots expose operational notes. OCR needs correction and may
misread logos/layouts/currency. These are documented scaffold limits, not claims
that live systems were tested.

The user's conditional authorization permits commit/push after checks pass. Use a
reviewable codex/menu-service-integration branch, preserve main and the existing
menu+integration worktree, and verify the pushed remote SHA. Remote CI status is
reported after push rather than presumed from local checks.
