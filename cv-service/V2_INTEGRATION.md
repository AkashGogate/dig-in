# Canonical v2 CV integration

The active application is `backend/app/mvp/Restaurant`, not the separately
preserved `kitchen-backend`. The old engine/schema/tests remain available for
teammate reference and regression coverage. They do not receive active app orders.

## Run without cameras

Start the canonical app backend first. From `cv-service/`:

```bash
uv sync --locked
uv run python -m cvsvc.v2 --backend http://127.0.0.1:8000
```

This defaults to **manual mock** using `config/v2.yaml`, a synthetic six-zone A–F
layout. It opens no cameras and binds the producer API to loopback port8001. Use
its existing `/mock/bays/A/plates` delta control to add/remove a simulated plate.
The sidecar measures >=1500ms continuously sampled stability and sends a frozen,
simulated envelope into canonical `/api/v2/cv/observations`. The app retains its
normal Server/Kitchen manual controls, readiness counts and notification rules.
The canonical app emits/exports its own accepted/observed facts.

If the app has full-site Basic authentication configured, supply the same
`DEMO_AUTH_USER` and `DEMO_AUTH_PASS` environment variables to the local worker.
Both must be set or both absent; secrets never enter URLs or logs. The worker
obtains a cook demo session and uses the authenticated app session endpoints.
No billable cloud service is called by this worker.

## Explicit hardware mode

`--camera` is opt-in. First calibrate **all six** physical zones, capture empty
references and configure real camera sources/geometry. The committed v2 polygons
are synthetic examples, not the real rig's calibration. The old committed
calibration PNGs were real camera frames and are removed from the integrated tip;
local calibration PNGs are ignored. History is preserved, not rewritten.

Hardware mode requires a local MediaPipe HandDetector model at
`ingredient.hand_model_path` (existing producer README gives its official source).
No model is downloaded automatically. Missing hand model or reference prevents
startup. A runtime frame/reference shape mismatch refuses the first-frame-as-empty
fallback. Motion alone never proves no hand: the actual hand detector is sampled
for plating, and motion additionally suppresses evidence. Confidence is preserved;
<0.7 evidence does not advance readiness. Keep detector max_plates_per_bay >=2 so
multiple plates remain detectable; canonical operational occupancy still allows1.

No live camera/model/rig throughput or accuracy claim is made. The canonical
runner disables raw/overlay MJPEG and binds to loopback; do not publicly deploy
the original unauthenticated debug/calibration producer API. No dining-room view,
face identification or raw recording is needed. Recording tools remain deliberate
local tools; no source videos/private frames were used in integration tests.

## Evidence, failure and recovery contract

- Actual event shape remains `cvsvc/events.py`, with its generated schema in
  `schema/events.schema.json`. Backend loads this owning source, not copied models.
- `GET /api/v2/cv/context` exposes the current physical assignment identities and
  versions, stable threshold, camera map, and latest explicit reconciliation token.
- `POST /api/v2/cv/observations` accepts `{event,run_id,simulated,binding?,evidence?}`.
  Plating requires capture-time `{zone_id,assignment_version,order_id,dish_id}` and
  measured `{stable_ms,hand_present}`. One configured bay maps to one physical unit.
  Unversioned legacy snapshots are not automatic readiness/pickup evidence.
- Sampler uses monotonic dwell, resets on >350ms frame gaps, hand/motion/health or
  capture-binding changes, and refuses stale context. An occupied old binding must
  see stable empty before a newly assigned unit can become ready. Ignored hand/
  low-confidence samples never erase verified occupied history.
- Bad camera health/recovery recount quarantines source zones until explicit staff
  reconciliation or tap pickup recovery is visible in canonical context. Stable
  emptiness and fresh assignment evidence are still required afterward. Plates
  removed during blockage cannot silently become pickups on camera recovery.
- The backend requires source-time freshness, exact camera/source/unit correlation,
  versions, one-plate counts, confidence and stability. It sends validated commands
  through `Restaurant.execute`; it never directly changes order/zone/stock state.
  Stale/invalid evidence is rejected, not relabeled accepted.
- Heartbeat expiry after10s uses the same Core camera-status command and marks
  occupancy unknown, never empty. The router lifespan owns this watchdog.
- Ingredient trips, counts and pending changes return `review_required`; no recipe
  or inventory deduction occurs. A proper countable reviewed stock adapter remains
  separate work. The old standalone backend's trip deduction is not activated.
- Delivery queues **individual complete envelopes**, retaining original event ID,
  source time and binding across retries. Terminal stale/invalid rejection records
  local review metadata and does not drop unrelated queued entries. Queue/review
  records are bounded and in memory; restart loses pending work (no durability
  promise). A full queue withholds evidence and requires manual recovery.

## Packaging / application splice

Canonical app composition includes
`create_cv_router(lambda: mvp_api.restaurant)` from `app.mvp.cv_api`; app-wide auth
must wrap it. Package the owning `cv-service/cvsvc/events.py` at
`/app/cvsvc/events.py` in the backend image. The backend bridge only needs existing
Pydantic dependencies, not OpenCV or MediaPipe. CV tools run in their own locked
environment; independent kitchen-backend is not started by the app deployment.

## Executed evidence

macOS/Python3.11.18 locked CV and standalone kitchen environments installed. CV
synthetic image counting/hand tests/replay tools/mock API suite plus new v2
regressions pass. New tests exercise continuous measured dwell, low confidence,
source context changes, no first-frame calibration fallback, native two-plate
counts, individual-rejection queue preservation and the actual producer mock API
→ canonical Restaurant ready/pickup loop, including blocked→tap pickup recovery→
new allocation→stable empty→new ready. No private frames or live rigs were run.

## Incremental shape branch (7e13c16)

The new `circles` detector and its synthetic pattern/texture tests are preserved.
Canonical `config/v2.yaml` stays on calibrated `bays`; circles remains an explicit
configuration choice, not a claimed live accuracy upgrade. In canonical circles
mode, each frame is cross-checked against the calibrated per-bay counter. Only
matching counts carry that counter's confidence; disagreement (including a false
empty) is withheld. Circle footprints must be fully contained in one physical
zone; overlap/boundary/gap ambiguity withholds every touched zone, including a
neighbour whose centre-based circle count is zero. Plate overflow remains visible.
Hough's quality threshold is a detector setting, not a calibrated probability.

Incoming legacy health can accept a still rearranged scene after5s; canonical v2
explicitly disables that rebaselining. A stationary obstruction/camera move never
becomes a trusted empty calibration automatically. Existing reference, hand,
continuous-dwell, confidence, quarantine, version and explicit recovery gates stay
in place. Legacy kitchen auto-active-ticket advance is preserved/tested only in
`kitchen-backend`; no new queued v2 order auto-start or recipe deduction is wired.

Increment validation: full CV55passed, standalone kitchen49passed, canonical bridge12passed; physical rig remains untested.
