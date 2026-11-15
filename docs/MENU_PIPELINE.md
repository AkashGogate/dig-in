# Mutable menus and encoding

Menu/Core owns this pipeline and the shared backend integration. Supported menu
inputs become canonical `MenuDocument` records and vectors without adding dish
names to parser/domain code. Prices, recipes, modifiers, stations, typical times
and ingredient geometry are never inferred from customer descriptions.

## Working inputs

- JSON: an existing canonical document, a list of item names, or an object with
  `name` and `items`. Each item is a name string or an object with `name` and
  optional canonical fields (`id`, `aliases`, `description`, `category`, etc.).
  Missing menu/item IDs are generated deterministically. Duplicate IDs fail.
- CSV: `name` is required; optional headers are `id`, `description`, `category`,
  `price_cents`, `aliases`. Cents are integers; separate aliases with semicolons.
  JSON supports the full nested modifier/recipe fields.
- Plain text: **one item per nonblank line**, either `Name` or
  `Name | Description`. Do not include headings/prices as separate lines.

Structured preparation accepts at most 100,000 characters and 500 items.
PDF/PNG/JPEG uploads now extract provisional dishes locally and show editable
name/description/price rows before encoding. See [MENU_EXTRACTION](MENU_EXTRACTION.md)
for dependencies, limits, correction flow and OCR uncertainty. Arbitrary document
layout accuracy is not guaranteed; compare against the original.

`backend/fixtures/menus/dig-in.json` carries all eight dishes from the existing
DIG IN artwork/prompt. Its aliases are explicit demo configuration; unspecified
prices, modifiers and kitchen fields stay unknown/empty. It is opt-in so the
original two-dish smoke/regression fixture remains available.

## Prepare offline

From `backend/`, using the normal locked environment:

```bash
uv run python -m scripts.menu_tool fixtures/menus/dig-in.json --output outputs/reviewed-menu.json
# Or your own menu:
uv run python -m scripts.menu_tool /path/to/menu.csv --name "New cafe" --output outputs/cafe.json
```

The tool creates canonical JSON and an adjacent `.index.json` inspection
artifact, and prints warnings/missing fields. It refuses existing output paths.
It does not change a running backend. Review the JSON, then set
`DIG_IN_MENU_PATH=outputs/reviewed-menu.json` for the next startup. Startup builds
an index from the configured menu; index artifacts are not trusted input files.

## Change a running backend

Use **Menu setup** in the app navigation (or **Upload & review a menu** on the
Server screen). Choose **Integration demo lead** in the session picker and enter
the demo session to enable menu changes.

1. Choose a JSON, CSV or TXT file: reading and encoding start automatically. Or
   paste content, choose its format/name, and select **Prepare & encode menu**.
2. Review every dish, price, alias, modifier and unknown kitchen field. Shared
   aliases appear as matching warnings. Open Kitchen & recipe details where needed.
3. Check **I reviewed every item…**, then select **Activate menu**. The result names
   the active menu; new orders use it while open drafts/tickets retain their menu.
4. To correct the menu, edit the input and prepare again. Any input/session change
   clears the old preview/review. If another device changes the active menu, prepare
   and review again. If activation has an uncertain result, use **Retry last event**
   above; it reuses the exact activation envelope.

The screen shows lead restrictions, validation/provider/connection errors, encoding
progress and success. Uploaded/pasted text is not saved in browser storage. PDF/photo extraction is available with the local OCR runtime described above. Runtime activation is still in-memory; a
backend restart loads its configured startup JSON. The API/CLI remain available
for adapters and scripted setup. The underlying API flow is:

1. `POST /api/v2/sessions` with `{"actor_id":"lead-1"}` obtains a **demo** lead
   session. This is not production authentication.
2. `POST /api/v2/menu/prepare`, header `X-Demo-Session`, accepts
   `{"content":"[\"Tomato soup\",\"Basil pasta\"]","media_type":"application/json","name":"Cafe"}`.
   It normalizes/validates/encodes outside the operational lock and returns
   `candidate_id`, `expected_menu_revision`, canonical `menu`, index metadata,
   ambiguous alias warnings and missing kitchen fields. Active state is untouched.
3. A human reviews those records. Send the usual v2 command envelope to
   `POST /api/v2/commands` with tap source, a new event ID/source timestamp, and:

   ```json
   {
     "action": "activate_menu",
     "candidate_id": "<prepared candidate_id>",
     "expected_menu_revision": "<prepared expected_menu_revision>",
     "human_confirmed": true
   }
   ```

4. Core checks lead/tap/review, candidate availability and the expected active
   revision under its lock. It commits menu + index selection + canonical
   `menu.activated` event/outbox through the existing transaction. Keep the exact
   command envelope on retry. A stale candidate gets 409: prepare/review again.

Candidate preparation keeps only normalized menu/vector data, with the latest
16 candidates in memory. Unknown/evicted candidates require preparing again.
Content SHA-256 is the menu revision (including descriptions, aliases and kitchen
fields). All activated revisions remain in process memory for open/historical
orders. Restart loses runtime activations/candidates; use reviewed JSON for
startup persistence. No durable store/auth/multi-worker guarantee is added.

## Matching and embeddings

- `GET /api/v2/menu/index`: current revision, provider, vector dimension, item
  count, semantic/baseline distinction and candidate-only policy.
- `POST /api/v2/menu/search`: `{text, menu_revision?, limit?}` plus any valid demo
  session. Returns ranked menu IDs and cosine scores; **scores are not calibrated
  confidence**. A removed item can be searched in its historical revision.
- `POST /api/v2/menu/match`: deterministic aliases remain authoritative for
  draft construction. On unknown phrases, vectors add **suggestions only**.
- Voice capture uses only local suggestions, never network embeddings while
  Core's lock is held. Unknown/ambiguous items/modifiers/table flags still block
  human Confirm. Kitchen speech retains exact matching and ambiguity checks.

Default `DIG_IN_EMBEDDINGS_MODE=local` uses deterministic 512-dimensional word/
character feature hashing. It works offline and exercises vector plumbing, but
is **not a trained semantic AI model** and has no synonym/accuracy guarantee.
`EmbeddingProvider.encode` is the replaceable provider boundary.

An implemented, **opt-in and unverified live**, OpenAI adapter uses the
[official embeddings request/response contract](https://developers.openai.com/api/reference/resources/embeddings/methods/create).
To deliberately enable it, configure all three variables on the backend:

```dotenv
DIG_IN_EMBEDDINGS_MODE=openai
DIG_IN_EMBEDDINGS_MODEL=text-embedding-3-small
DIG_IN_EMBEDDINGS_API_KEY=<server-side key>
```

This sends menu name/alias/description/category strings on startup/preparation
and sends the caller's text on **explicit `/menu/search` calls**, with potential
provider charges and provider retention policies. It never automatically sends
voice capture transcripts. Do not pass full read-backs/audio to search. No
provider call, credentials or model download is needed in local mode. Live
provider enablement/quality/latency and deployment access controls need separate
verification before public use. Tests use `httpx.MockTransport`, not paid calls.

Provider errors or malformed/zero/non-finite/dimension-mismatched vectors fail
preparation/search with 503. Failed preparation leaves the active menu usable.
Configured remote startup encoding is fail-fast; use local mode if unavailable.
No automatic downgrade mislabels lexical vectors as semantic vectors.

## Integration guarantees and review boundaries

Orders pin a menu revision **when the draft starts**, so existing drafts, their
manual selectors/voice matcher, and submitted tickets retain their original
menu even when names/IDs/modifiers change. New orders use the new menu. Name,
modifier labels, station/time/recipe/price snapshots stay stable; kitchen speech
resolves against each eligible order's menu. Recipe expectations use that same
revision, rather than the current menu's ingredient map. Existing physical
ingredient zones/balances are preserved: activation rejects new/remapped zones
until explicit physical setup is implemented. Expected recipes do not deduct stock.

V2 gains compatible fields (`description`, `category`, `menu_revision`, `menus`,
`modifier_names`) and an additive `activate_menu` command/event. `/contracts`
exposes menu/import/search schemas alongside operational/event schemas. Voice
consumes an optional suggestion callback; CV assignment/readiness commands are
unchanged. Databricks receives `menu.activated` and submitted menu revision but
needs no menu text, queries or transcript exports. Dependent Voice/Databricks and
shared-client review is still needed before team merge; local integration tests
are not another teammate's signoff.
