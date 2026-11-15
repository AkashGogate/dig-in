"""Camera pipelines: one worker thread per camera running the ingredient and/or plating
modules, health checks, periodic snapshots, heartbeats and the debug overlay."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Any, Iterator

import cv2
import numpy as np

from cvsvc import debug
from cvsvc.config import CVConfig
from cvsvc.context import ContextStore
from cvsvc.emitter import Emitter
from cvsvc.events import EventBus
from cvsvc.health import HealthMonitor
from cvsvc.ingredient.tracker import ZoneTracker
from cvsvc.ingredient.hands import HandTripTracker, zone_of
from cvsvc.ingredient.trips import TripTracker
from cvsvc.ingredient.zones import ZoneCounter
from cvsvc.plating.bays import BayCounter, PlateCount
from cvsvc.plating.circles import PlateFinder, assign_to_bays
from cvsvc.plating.tracker import BayTracker
from cvsvc.sources import FrameSource
from cvsvc.vision import MotionDetector, PresenceDetector, mean_luminance

log = logging.getLogger(__name__)


def reference_path(cfg: CVConfig, camera_id: str) -> Path:
    return Path(cfg.calibration_dir) / f"{camera_id}.png"


class _Zone:
    def __init__(self, zcfg, reference, icfg, gray_shape) -> None:
        self.cfg = zcfg
        self.trips_mode = icfg.mode == "trips"
        self.counter = ZoneCounter(zcfg, reference)
        self.motion = MotionDetector(self.counter.mask, icfg.motion_min_area_px)
        self.trip = TripTracker(min_trip_s=icfg.min_trip_s, settle_s=icfg.trip_settle_s,
                                max_trip_s=icfg.occlusion_timeout_s)
        self.hand_trip = HandTripTracker(dwell_s=icfg.hand_dwell_s)
        self.hands_mode = icfg.trip_detector == "hands"
        # baseline is taken from the first live frame (see CameraWorker._process_zone)
        self.initialized = False
        self.tracker = ZoneTracker(baseline=0, settle_s=icfg.settle_s,
                                   occlusion_timeout_s=icfg.occlusion_timeout_s,
                                   large_delta_limit=icfg.large_delta_limit)
        self.last = None
        self.frozen_baseline: int | None = None

    @property
    def state(self) -> str:
        if self.trips_mode:
            return self.hand_trip.state if self.hands_mode else self.trip.state
        return self.tracker.state

    @property
    def trip_count(self) -> int:
        return self.hand_trip.trips if self.hands_mode else self.trip.trips


class _Bay:
    def __init__(self, bcfg, reference, pcfg) -> None:
        self.cfg = bcfg
        self.counter = BayCounter(bcfg, reference, pcfg.max_plates_per_bay)
        from cvsvc.vision import polygon_mask
        self.motion = MotionDetector(polygon_mask(reference.shape, bcfg.polygon), pcfg.motion_min_area_px)
        self.tracker = BayTracker(debounce_s=pcfg.debounce_s, occlusion_timeout_s=pcfg.occlusion_timeout_s)
        self.initialized = False
        self.last = None


class CameraWorker:
    def __init__(self, camera_id: str, owner: "CameraPipelines") -> None:
        self.id = camera_id
        self.o = owner
        self.cfg = owner.cfg
        self.ccfg = owner.cfg.cameras[camera_id]
        self.has_ingredient = owner.cfg.ingredient.camera == camera_id and bool(owner.cfg.ingredient.zones)
        self.has_plating = owner.cfg.plating.camera == camera_id and bool(owner.cfg.plating.bays)
        self.health = HealthMonitor(owner.cfg.health)
        self.zones: dict[str, _Zone] = {}
        self.bays: dict[str, _Bay] = {}
        self.reference: np.ndarray | None = None
        self.lock = threading.Lock()
        self.overlay: np.ndarray = debug.placeholder(camera_id, "starting")
        self.raw: np.ndarray = self.overlay
        self.overlay_seq = 0
        self.fps = 0.0
        self.capture_request: threading.Event | None = None
        self.capture_done = threading.Event()
        self.captured_path: str | None = None
        self.recovering_since: float | None = None
        self.occluded_bays: set[str] = set()
        self.scene_motion: PresenceDetector | None = None
        self.body_until = 0.0
        self.hand_detector = None
        self.hands: list = []
        pc = self.cfg.plating
        self.plate_finder = PlateFinder(pc.plate_min_radius_px, pc.plate_max_radius_px, pc.circle_quality) \
            if self.has_plating and pc.detector == "circles" else None
        if self.has_ingredient and self.cfg.ingredient.mode == "trips" and self.cfg.ingredient.trip_detector == "hands":
            from cvsvc.ingredient.hands import HandDetector
            self.hand_detector = HandDetector(self.cfg.ingredient.hand_model_path)
        self.stop = threading.Event()

    # ---- emit helpers ----
    def emit(self, ev) -> None:
        self.o.bus.publish_threadsafe(ev)

    def emit_status(self, ts: float, heartbeat: bool = False) -> None:
        state, reason = self.health.state, self.health.reason
        if state == "ok" and self.occluded_bays:
            state, reason = "degraded", "bay_occluded:" + ",".join(sorted(self.occluded_bays))
        self.emit(self.o.emitter.camera_status(self.id, state, reason, self.health.since or ts, heartbeat=heartbeat))

    # ---- setup ----
    def _load_reference(self, first_frame: np.ndarray) -> np.ndarray:
        p = reference_path(self.cfg, self.id)
        if p.exists():
            ref = cv2.imread(str(p))
            if ref is not None and ref.shape == first_frame.shape:
                return ref
        if getattr(self.o, "v2_require_reference", False):
            raise ValueError("Canonical CV requires a matching, explicitly calibrated empty reference")
        log.warning("%s: missing/mismatched empty reference %s; using first frame in legacy mode", self.id, p)
        return first_frame.copy()

    def _build(self, reference: np.ndarray) -> None:
        self.reference = reference
        self.health.set_reference(reference)
        if self.has_ingredient:
            self.zones = {z.id: _Zone(z, reference, self.cfg.ingredient, reference.shape) for z in self.cfg.ingredient.zones}
        if self.has_plating:
            self.bays = {b.id: _Bay(b, reference, self.cfg.plating) for b in self.cfg.plating.bays}

    def set_reference(self, frame: np.ndarray) -> str:
        p = reference_path(self.cfg, self.id)
        p.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(p), frame)
        with self.lock:
            self.reference = frame.copy()
            self.health.set_reference(frame)
            for z in self.zones.values():
                z.counter.set_reference(frame)
            for b in self.bays.values():
                b.counter.set_reference(frame)
        return str(p)

    # ---- main loop ----
    def run(self) -> None:
        src = FrameSource(self.ccfg.source, tuple(self.ccfg.resolution), self.ccfg.fps_target, self.ccfg.loop)
        period = 1.0 / max(self.ccfg.fps_target, 1)
        last_hb = last_snap = 0.0
        fps_t, fps_n = time.time(), 0
        self.emit_status(time.time())
        while not self.stop.is_set():
            t0 = time.time()
            frame = src.read()
            if frame is None:
                tr = self.health.tick(t0)
                if tr:
                    self._on_transition(tr, t0)
                with self.lock:
                    self.overlay = debug.placeholder(self.id, f"no frame ({self.health.state})")
                    self.overlay_seq += 1
                if src.finite and not src.loop:
                    log.info("%s: source ended", self.id)
                    self.stop.wait(1.0)
                else:
                    self.stop.wait(0.5)
                    if self.health.state == "lost":
                        src.release()
                        src = FrameSource(self.ccfg.source, tuple(self.ccfg.resolution), self.ccfg.fps_target,
                                          self.ccfg.loop)
            else:
                if self.reference is None:
                    self._build(self._load_reference(frame))
                if self.capture_request is not None and self.capture_request.is_set():
                    self.captured_path = self.set_reference(frame)
                    self.capture_request = None
                    self.capture_done.set()
                self.process(t0, frame)
                fps_n += 1
            if t0 - last_hb >= self.cfg.health.heartbeat_s:
                last_hb = t0
                self.emit_status(t0, heartbeat=True)
            if t0 - last_snap >= self._snapshot_interval() and not self.health.frozen and self.reference is not None:
                last_snap = t0
                self.snapshots(t0)
            if time.time() - fps_t >= 1.0:
                self.fps = fps_n / (time.time() - fps_t)
                fps_t, fps_n = time.time(), 0
            dt = period - (time.time() - t0)
            if dt > 0:
                self.stop.wait(dt)
        src.release()

    def _snapshot_interval(self) -> float:
        vals = []
        if self.has_ingredient:
            vals.append(self.cfg.ingredient.snapshot_interval_s)
        if self.has_plating:
            vals.append(self.cfg.plating.snapshot_interval_s)
        return min(vals) if vals else 10.0

    def snapshots(self, ts: float) -> None:
        for zid, z in self.zones.items():
            if not z.trips_mode and z.tracker.state == "stable":
                self.emit(self.o.emitter.zone_snapshot(zid, z.cfg.ingredient, z.tracker.baseline, ts=ts))
        for bid, b in self.bays.items():
            self.emit(self.o.emitter.bay_state(bid, b.tracker.stable_count, ts=ts))

    def _on_transition(self, tr, ts: float) -> None:
        log.info("%s: camera %s (%s)", self.id, tr.state, tr.reason)
        self.emit_status(ts)
        if tr.state in ("obstructed", "lost"):
            # freeze: hold last baselines; reconciliation happens after recovery (see process())
            self.recovering_since = None
            for z in self.zones.values():
                if z.frozen_baseline is None:
                    z.frozen_baseline = z.tracker.baseline

    def process(self, ts: float, frame: np.ndarray) -> None:
        with self.lock:
            any_active = any(z.state in ("active", "settling") for z in self.zones.values()) or \
                any(b.tracker.state != "stable" for b in self.bays.values())
            was_frozen = self.health.frozen and self.reference is not None
            tr = self.health.update(ts, frame, any_zone_active=any_active)
            if tr:
                self._on_transition(tr, ts)
                if was_frozen and not self.health.frozen:
                    self.recovering_since = ts
            if self.health.frozen:
                self._render(frame)
                return
            if self.recovering_since is not None:
                # CV_SPEC 9: after recovery wait, re-measure and reconcile instead of silently accepting
                if ts - self.recovering_since < self.cfg.health.recovery_wait_s:
                    self._render(frame)
                    return
                self._reconcile(ts, frame)
                self.recovering_since = None
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if self.cfg.ingredient.mode == "trips" and self.hand_detector is not None:
                self._process_hand_trips(ts, frame)
            elif self.cfg.ingredient.mode == "trips":
                self._process_trips(ts, gray)
            else:
                for zid, z in self.zones.items():
                    self._process_zone(ts, frame, gray, zid, z)
            if getattr(self.o, "v2_sampler", None) is not None and self.has_plating:
                detector = getattr(self.o, "v2_hand_detector", None)
                self.v2_hand_present = bool(detector.detect(frame, ts)) if detector is not None else None
            per_bay = self._circle_counts(frame) if self.plate_finder is not None else None
            for bid, b in self.bays.items():
                self._process_bay(ts, frame, gray, bid, b, per_bay[bid] if per_bay else None)
            self._render(frame)

    def _process_zone(self, ts, frame, gray, zid, z: _Zone) -> None:
        motion = z.motion.update(gray)
        zc = z.counter.count(frame)
        z.last = zc
        if not z.initialized:
            z.initialized = True
            z.tracker.resolve(zc.count, mean_luminance(frame, z.counter.mask))
            self.emit(self.o.emitter.zone_snapshot(zid, z.cfg.ingredient, zc.count, ts=ts))
            return
        res = z.tracker.update(ts, zc.count, motion, mean_luminance(frame, z.counter.mask),
                               self.o.context.active_version())
        if res is None:
            return
        attr = self.o.context.attribution(res.version_at_start)
        em = self.o.emitter
        if res.kind == "picked":
            self.emit(em.picked(zid, z.cfg.ingredient, res.before, res.after, res.confidence, attr, ts))  # type: ignore[arg-type]
        elif res.kind == "returned":
            self.emit(em.returned(zid, z.cfg.ingredient, res.before, res.after, res.confidence, attr, ts))  # type: ignore[arg-type]
        else:
            self.emit(em.pending(zid, z.cfg.ingredient, res.reason or "unstable_count", res.before, res.after,
                                 res.confidence, attr, ts))

    def _scene_moving_fraction(self, gray) -> float:
        """Share of the frame occupied by something that isn't normally there (a person)."""
        if self.scene_motion is None:
            self.scene_motion = PresenceDetector()
        return self.scene_motion.update(gray)

    def _process_trips(self, ts, gray) -> None:
        motions = {zid: z.motion.update(gray) for zid, z in self.zones.items()}
        icfg = self.cfg.ingredient
        if self._scene_moving_fraction(gray) > icfg.body_motion_fraction:
            self.body_until = ts + icfg.body_hold_s
        # fraction of each zone's area that is moving; the largest moving fraction is "dominant"
        frac = {zid: z.motion.last_area / max(1, int((z.motion.mask > 0).sum())) for zid, z in self.zones.items()}
        moving = [zid for zid, m in motions.items() if m]
        dominant = max(moving, key=lambda zid: frac[zid]) if moving else None
        crowded = sum(1 for zid in moving if frac[zid] > 0.3) >= 3 or ts < self.body_until
        version = self.o.context.active_version()
        for zid, z in self.zones.items():
            res = z.trip.update(ts, motions[zid], dominant == zid, crowded, version)
            if res is None:
                continue
            attr = self.o.context.attribution(res.version_at_start)
            self.emit(self.o.emitter.trip(zid, z.cfg.ingredient, res.duration_s, res.confidence, attr,
                                          res.reason, ts))

    def _process_hand_trips(self, ts, frame) -> None:
        assert self.hand_detector is not None
        icfg = self.cfg.ingredient
        self.hands = [h for h in self.hand_detector.detect(frame, ts) if h.size <= icfg.hand_max_size_px]
        polys = {zid: np.array(z.cfg.polygon, np.int32) for zid, z in self.zones.items()}
        occupied = {zone_of(h, polys) for h in self.hands} - {None}
        version = self.o.context.active_version()
        for zid, z in self.zones.items():
            res = z.hand_trip.update(ts, zid in occupied, version)
            if res is None:
                continue
            attr = self.o.context.attribution(res.version_at_start)
            self.emit(self.o.emitter.trip(zid, z.cfg.ingredient, res.duration_s, res.confidence, attr, None, ts))

    def _circle_counts(self, frame) -> dict[str, PlateCount]:
        assert self.plate_finder is not None
        polys = {bid: np.array(b.cfg.polygon, np.int32) for bid, b in self.bays.items()}
        plates = self.plate_finder.find(frame)
        by_bay = assign_to_bays(plates, polys)
        self.v2_circle_ambiguous = set()
        if getattr(self.o, "v2_sampler", None) is not None:
            # Centre assignment remains the teammate's legacy convention. In v2
            # a footprint crossing a physical zone boundary cannot prove either
            # one unit in that zone or empty space in its neighbour.
            for plate in plates:
                distances = {bid: cv2.pointPolygonTest(poly, (float(plate.x), float(plate.y)), True)
                             for bid, poly in polys.items()}
                touched = {bid for bid, distance in distances.items() if distance > -plate.r}
                contained = {bid for bid, distance in distances.items() if distance >= plate.r}
                if touched and (len(touched) > 1 or len(contained) != 1):
                    self.v2_circle_ambiguous.update(touched)
        cap = self.cfg.plating.max_plates_per_bay
        return {bid: PlateCount(min(len(ps), cap), 1.0, [p.contour() for p in ps]) for bid, ps in by_bay.items()}

    def _bay_count(self, frame, b: _Bay) -> PlateCount:
        if self.plate_finder is not None:
            return self._circle_counts(frame)[b.cfg.id]
        return b.counter.count(frame)

    def _process_bay(self, ts, frame, gray, bid, b: _Bay, precomputed: PlateCount | None = None) -> None:
        motion = b.motion.update(gray)
        pc = precomputed if precomputed is not None else b.counter.count(frame)
        if precomputed is not None and getattr(self.o, "v2_sampler", None) is not None:
            # Hough ALT returns geometry, not calibrated probabilities. Reuse the
            # same-frame calibrated counter's confidence only when counts agree.
            calibrated = b.counter.count(frame)
            reliable = (calibrated.count == pc.count
                        and bid not in getattr(self, "v2_circle_ambiguous", set())
                        and self.cfg.plating.max_plates_per_bay >= 2)
            pc = PlateCount(pc.count, calibrated.confidence if reliable else 0.0, pc.contours)
        b.last = pc
        # Optional v2 bridge consumes per-frame evidence before legacy debounce.
        # It captures unit/version context at candidate start and measures its own
        # canonical dwell. Periodic legacy BAY_STATE is never stability proof.
        sampler = getattr(self.o, "v2_sampler", None)
        if sampler is not None:
            hand = getattr(self, "v2_hand_present", None)
            sampler(bid, ts, pc.count, motion or hand is not False, self.health.state, pc.confidence)
        if not b.initialized:
            b.initialized = True
            b.tracker.stable_count = pc.count
            self.emit(self.o.emitter.bay_state(bid, pc.count, pc.confidence, ts=ts))
            return
        u = b.tracker.update(ts, pc.count, pc.confidence, motion)
        if u.occluded_timeout:
            self.occluded_bays.add(bid)
            self.emit_status(ts)
        if u.occlusion_cleared:
            self.occluded_bays.discard(bid)
            self.emit_status(ts)
        if u.change:
            em = self.o.emitter
            if u.change.kind == "arrived":
                self.emit(em.plate_arrived(bid, u.change.before, u.change.after, u.change.confidence, ts))
            else:
                self.emit(em.plate_removed(bid, u.change.before, u.change.after, u.change.confidence, ts))
            self.emit(em.bay_state(bid, u.change.after, u.change.confidence, ts=ts))

    def _reconcile(self, ts: float, frame: np.ndarray) -> None:
        em = self.o.emitter
        for zid, z in self.zones.items():
            if z.trips_mode:
                continue  # trips carry no counts; nothing to reconcile
            now_count = z.counter.count(frame).count
            before = z.frozen_baseline if z.frozen_baseline is not None else z.tracker.baseline
            z.frozen_baseline = None
            if now_count != before and z.tracker.state != "pending":
                z.tracker.state = "pending"
                self.emit(em.pending(zid, z.cfg.ingredient, "post_obstruction_mismatch", before, now_count, 0.5,
                                     self.o.context.attribution(), ts))
        for bid, b in self.bays.items():
            now_count = self._bay_count(frame, b).count
            changed = now_count != b.tracker.stable_count
            b.tracker.stable_count = now_count
            b.tracker.candidate = None
            self.emit(em.bay_state(bid, now_count, note="post_obstruction_recount" if changed else None, ts=ts))
        if self.bays:
            self.emit(em.camera_status(self.id, self.health.state, "recovered_recount", self.health.since or ts))

    def _render(self, frame: np.ndarray) -> None:
        self.raw = frame
        img = frame.copy()
        for zid, z in self.zones.items():
            if z.trips_mode:
                debug.draw_trip_zone(img, z.cfg.polygon, z.state, zid, z.cfg.ingredient, z.trip_count)
            elif z.last is not None:
                debug.draw_zone(img, z.cfg.polygon, z.tracker.state, zid, z.cfg.ingredient, z.tracker.baseline,
                                z.counter.slot_polygons(), z.last.occupied)
        for bid, b in self.bays.items():
            state = b.tracker.state
            debug.draw_bay(img, b.cfg.polygon, state, bid, b.tracker.stable_count, self.o.context.bay(bid),
                           b.last.contours if b.last else [])
        for h in self.hands:
            debug.draw_hand(img, h.points, h.tip)
        debug.draw_banner(img, self.id, self.health.state, self.health.reason, self.fps)
        self.overlay = img
        self.overlay_seq += 1


class CameraPipelines:
    def __init__(self, cfg: CVConfig, bus: EventBus, context: ContextStore, emitter: Emitter) -> None:
        self.cfg = cfg
        self.bus = bus
        self.context = context
        self.emitter = emitter
        used = {cfg.ingredient.camera if cfg.ingredient.zones else None,
                cfg.plating.camera if cfg.plating.bays else None} - {None}
        missing = used - set(cfg.cameras)
        if missing:
            raise ValueError(f"cameras {missing} referenced but not defined under `cameras:`")
        self.workers = {cid: CameraWorker(cid, self) for cid in sorted(used)}  # type: ignore[type-var]
        self.threads: list[threading.Thread] = []

    async def run(self) -> None:
        for w in self.workers.values():
            t = threading.Thread(target=w.run, name=f"cam-{w.id}", daemon=True)
            t.start()
            self.threads.append(t)
        try:
            await asyncio.Event().wait()
        finally:
            for w in self.workers.values():
                w.stop.set()

    def _zone_worker(self, zone_id: str) -> tuple[CameraWorker, Any]:
        for w in self.workers.values():
            if zone_id in w.zones:
                return w, w.zones[zone_id]
        raise KeyError(zone_id)

    async def resolve_zone(self, zone_id: str, count: int) -> None:
        w, z = self._zone_worker(zone_id)
        with w.lock:
            z.tracker.resolve(count)
            z.frozen_baseline = None
        await self.bus.publish(self.emitter.zone_snapshot(zone_id, z.cfg.ingredient, count))

    async def capture_reference(self, camera_id: str) -> str:
        w = self.workers[camera_id]
        w.capture_done.clear()
        w.capture_request = threading.Event()
        w.capture_request.set()
        ok = await asyncio.to_thread(w.capture_done.wait, 5.0)
        if not ok:
            raise TimeoutError("no frame within 5 s")
        return w.captured_path or ""

    def mjpeg(self, camera_id: str, raw: bool = False) -> Iterator[bytes]:
        w = self.workers[camera_id]

        def gen():
            seen = -1
            while True:
                if w.overlay_seq != seen:
                    seen = w.overlay_seq
                    jpg = debug.encode_jpeg(w.raw if raw else w.overlay, 90 if raw else 70)
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                time.sleep(0.05)
        return gen()

    def health(self) -> dict[str, Any]:
        return {cid: {"state": w.health.state, "reason": w.health.reason, "fps": round(w.fps, 1),
                      "luminance": round(w.health.last_lum, 1), "focus": round(w.health.last_focus, 1),
                      "reference_loaded": w.reference is not None}
                for cid, w in self.workers.items()}
