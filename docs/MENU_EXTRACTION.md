# PDF/photo extraction and correction

## App workflow

Enter a demo lead session → Menu setup → upload PDF/PNG/JPEG → wait for local
extraction → compare with the original → edit dish names/descriptions/prices,
remove false positives, add missing dishes → Prepare & encode → review → Activate.
The existing structured JSON/CSV/TXT flow continues to work.

PDF/photo proposals are deliberately **not encoded or activated automatically**
before correction. The editable rows produce ordinary structured menu JSON in the
source textarea. Editing rows or source invalidates the encoded candidate, so
activation always refers to the newly reviewed, prepared revision. Prices in the
editor are integer cents, blank means unknown. Check the currency yourself; the
existing app displays USD. Recipes, modifiers, allergens, stations and typical
minutes are not inferred. Use canonical JSON to configure reviewed kitchen fields.

OCR can merge columns, split dishes, omit words, or identify logos as dishes.
The actual test menu yielded eight dishes plus a false-positive logo; removing
that ninth proposal was part of the real browser verification. This is useful
local OCR plus heuristic line grouping, not a guarantee of menu understanding.

## Runtime requirements

- macOS: installed Swift/Xcode command-line tools, AppKit/PDFKit/Vision. The
  checked-in `backend/app/mvp/adapters/menu_ocr.swift` runs locally. First execution
  may compile framework caches and take longer. No paid service/key/model download.
- Linux: `poppler-utils` and `tesseract-ocr` on PATH. The Dockerfile installs them.
  This adapter rasterizes PDF pages and runs Tesseract. Container build and Linux
  OCR have not been executed in this task; tests verify the source seam and rules.
- `GET /api/v2/menu/extraction-status` reports readiness, provider and limits.
  Missing tools produce an actionable 503; JSON/CSV/TXT remain usable.

Supported document signatures: PDF, PNG, JPEG. Maximum 8 MiB, 10 unlocked PDF
pages, 100,000 OCR text characters, and 500 provisional dishes. Subprocesses have
bounded timeouts. Multi-column layouts/languages, rotation, poor lighting, giant
images and handwritten menus need real-world validation. HEIC/WebP are not added.

## Contract and ownership

`POST /api/v2/menu/extract` uses `X-Demo-Session` (lead), raw binary body and a
matching Content-Type. No multipart dependency is needed. Returns:

```json
{"items":[{"name":"Soup","description":"Tomatoes","price_cents":900}],
 "source_text":"OCR evidence for comparison", "page_count":1,
 "requires_human_review":true, "warnings":["Review OCR against original"]}
```

`items` are provisional import records, not MenuDocument or submitted orders.
The extract endpoint does not enqueue analytics or mutate restaurant/menu state.
Invalid format/signature/readability gets 422; oversized streamed body gets 413;
unavailable tools get 503; missing/non-lead demo session gets 409.
Uploaded bytes are processed in an automatically deleted temporary directory;
no source document or OCR text enters the canonical event log, persistent file
store or browser storage. OCR text remains in the current page for comparison
until cleared/reload. Demo identity is still not production authentication.

The local bridge uses Apple's [text recognition API](https://developer.apple.com/documentation/vision/vnrecognizetextrequest).
Replace `ocr_pages(bytes, media_type)` to integrate another OCR producer; preserve
its page/line result and failure semantics. Keep dish grouping separate from OCR,
and keep both outside Restaurant's lock. A future model extractor must return
reviewable evidence through this seam, never call activation or invent kitchen
facts. Menu/Core reviews changes to extraction/import/activation contracts.

## Evidence

119 backend tests pass, including invalid signature/size, grouping, missing tools,
empty output and lead-only extract-without-state-mutation. Actual Apple Vision
read the synthetic PNG and a generated one-page scanned PDF. Browser photo upload,
false-positive removal, name correction, preparation, review and activation
passed. Existing nine UI state checks still pass. No live semantic calls occurred.
