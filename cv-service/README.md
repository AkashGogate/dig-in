# cv-service

Watches two fixed kitchen cameras and emits typed, timestamped **observation events**
(`CV_SPEC.md`). It never decides ready/served/inventory; the kitchen backend does.

- Ingredient camera: fixed zones split into a slot grid; slot occupancy = portion count.
- Plating camera: fixed bays; per-bay plate count, arrivals and removals.
- Contract: `../schema/events.schema.json`, generated from `cvsvc/events.py`
  (`uv run python -m cvsvc.events` regenerates it; a test fails if it is stale).

## Run

```bash
uv sync
uv run python -m cvsvc.main --mock                      # no cameras: simulated kitchen
uv run python -m cvsvc.main --mock --backend-url http://localhost:8002/cv/events
uv run python -m cvsvc.main                             # real cameras from config/cv.yaml
uv run pytest
```

Port 8001 by default (`--port`, `--host`). The backend URL can also come from `BACKEND_URL`
or `sinks.backend_url` in the config.

### Mock mode
`--mock` reacts to the context the backend pushes: a bay assigned a ticket receives plates
one at a time up to `expected_plates`, is emptied ~3 s after a claim appears (or after 25 s
unclaimed), ingredient zones get random picks attributed to the active ticket, and an
occasional `INGREDIENT_CHANGE_PENDING`. `--mock-manual` turns the automation off; drive it with:

```bash
curl -XPOST localhost:8001/mock/bays/A/plates -H 'content-type: application/json' -d '{"delta": 1}'
curl -XPOST localhost:8001/mock/cameras/plating_cam -H 'content-type: application/json' -d '{"state":"obstructed","reason":"lens_covered"}'
```

## Ingredient trips (default)

The backend owns stock. With `ingredient.mode: trips` the camera reports one
`INGREDIENT_TRIP` per reach into a zone and the backend subtracts the recipe quantity.
`trip_detector: hands` (recommended for a straight-on camera) counts a trip only when a
detected hand stays inside a zone for `hand_dwell_s`; people walking past or standing in
front never count. It needs the MediaPipe hand model (not committed):

```bash
mkdir -p models && curl -L -o models/hand_landmarker.task \
  https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
```

`trip_detector: motion` uses plain motion in the zone (no model; only reliable when nobody
stands between the camera and the shelf). Bays: `detector: white` finds white plates on a
coloured counter and ignores the counter's texture and the camera's auto white balance.

Debug streams: `/debug/<camera>.mjpg` (overlay) and `/debug/<camera>.mjpg?raw=1` (raw frames,
for recording and replay).

## Calibrate (under 2 minutes per camera)

1. Mount the camera fixed, overhead or at a high angle; turn on the venue lighting.
2. `uv run python -m cvsvc.calibrate --camera plating_cam`
3. For each bay: click its 4 corners clockwise from top-left, press `n` for the next bay.
4. For ingredient zones (`--camera ingredient_cam`): same, then `+`/`-` (columns) and
   `]`/`[` (rows) until the grid lines sit on the tray dividers.
5. **Empty** every bay/zone and press `r` to capture the empty reference.
6. Press `s` to save, `q` to quit.

Lighting changed at the venue? Re-capture the reference without the GUI:
`curl -XPOST localhost:8001/calibrate/plating_cam/reference` (with the area empty).
Watch the overlay at `http://localhost:8001/debug/plating_cam.mjpg`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | service + per-camera status, fps, `boot_id` (changes on restart) |
| GET | `/state` | latest zone counts, bay states, camera states, current context |
| WS | `/events` | live stream of every event |
| GET | `/events/recent?n=100` | last N events |
| PUT/DELETE | `/context/active_ticket` | backend only |
| PUT | `/context/bays`, `/context/claims` | backend only, full replace |
| POST | `/zones/{id}/resolve` | `{count}`: staff correction of a zone baseline |
| POST | `/calibrate/{camera_id}/reference` | capture empty reference now |
| GET | `/debug/{camera_id}.mjpg` | overlay stream |

Every event is also appended to `logs/events.jsonl`. With a backend URL set, events are
POSTed in order; if the backend is down they queue in `logs/outbox.jsonl` and flush on
reconnect. Event ids are deterministic per physical change, so retries never duplicate.

## Evaluate

```bash
uv run python tools/label.py --source 1 --out recordings/run1      # record + key-press ground truth
uv run python tools/replay.py recordings/run1.mp4 --camera plating_cam --speed 0
uv run python tools/metrics.py logs/replay_events.jsonl recordings/run1.labels.jsonl
```

`metrics.py` prints a markdown table of measured numbers only (missed/false arrivals and
removals, plate-count accuracy, pick quantity errors, pending rate, obstruction latency and
false triggers). Nothing is estimated or hard-coded.

## How it works

- **Plates** (`plating/`): brightness-normalized Lab difference vs. the empty reference,
  morphology, contours filtered by area and circularity (>= 0.6); touching plates are split
  with a distance transform (lower confidence). Counts are suppressed while motion (a hand
  or arm) is in the bay and only accepted after holding for `debounce_s`.
- **Ingredients** (`ingredient/`): each zone is warped to a rectangle and split into slots;
  a slot is occupied when enough pixels differ from the reference. Per-zone state machine
  STABLE -> ACTIVE -> SETTLING -> resolve against the pre-interaction baseline; a hand alone
  never emits an event. Unstable counts, long occlusion or large deltas become
  `INGREDIENT_CHANGE_PENDING`, and the zone waits for `/zones/{id}/resolve`.
- **Health** (`health.py`): `lost` (no frames > 2 s), `obstructed` (dark, blurred relative to
  the reference, or most of the view blocked for 1.5 s while no zone is active), `degraded`
  (lighting/focus drift). While obstructed/lost no other events are emitted; on recovery it
  waits 2 s, re-measures, and emits `INGREDIENT_CHANGE_PENDING (post_obstruction_mismatch)` /
  `BAY_STATE (note: post_obstruction_recount)` instead of silently accepting changes.

## Assumptions (CV_SPEC 14 defaults, not yet confirmed)

- Backend ingest is plain HTTP POST of the event JSON (`kitchen-backend` `/cv/events`).
- Two USB webcams or phone cameras via an IP-camera app, fixed, consistent lighting.
- Demo ingredients are high-contrast countable items in a divided tray.
- Plates are plain, light-coloured and round, on a darker counter.
- No Arduino dependency.

Schema additions beyond the spec's table (both optional for consumers): `BAY_STATE.payload`
carries `expected_plates` (display only, per CV_SPEC 5) and `note`; `CAMERA_STATUS.payload`
carries `heartbeat` to distinguish the 5 s heartbeat from a transition.

Not built yet: M6 (optional YOLO detector).
