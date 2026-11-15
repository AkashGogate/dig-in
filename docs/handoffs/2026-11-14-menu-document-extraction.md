# PDF/photo extraction and agent integration

- Owner/claim: requested Menu/Core/backend integration; isolated clone branch
  codex/menu-document-extraction with prior uncommitted source as baseline.
- Paths: menu_extraction.py, adapters/menu_ocr.swift, api.py, Dockerfile,
  menu-document.js/setup/index, focused tests and navigation/integration docs.
- Contracts: additive lead-only raw-binary /menu/extract and GET extraction-status;
  provisional records/source text are never accepted menu/order facts. Existing
  canonical prepare/activate and exact retry contracts unchanged.
- Changes: local macOS Vision/PDFKit and Linux Poppler/Tesseract OCR seam, bounded
  file/page/text/time limits, temporary-file cleanup, editable add/remove/name/
  description/cents correction, review before encoding and activation. Agent task
  map and teammate integration guide make ownership, tests and source seams clear.
- Evidence: 119 backend tests; nine existing UI cases; scoped lint/format and JS
  syntax passed. Real Apple OCR PNG and scanned one-page PDF passed. Real browser
  removed OCR logo false positive, corrected name, encoded eight dishes, reviewed
  and activated. No paid integrations were enabled.
- Limits: arbitrary OCR layout/language accuracy is not proven. Linux OCR/Docker
  build untested locally. No new auth/persistence/distributed-state claims.
- Integration: preserve baseline/unrelated edits using content-hash checks. Shared
  API/client/Docker/doc changes need consumer review before team merge. No stage,
  commit, push or deployment performed; dependent lane review remains required.
