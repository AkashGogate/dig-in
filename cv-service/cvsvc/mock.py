"""--mock mode: a small simulated kitchen that emits contract-valid events.

It reacts to the context the backend pushes, so the full backend loop can be
exercised with no cameras:
  - a bay assigned a ticket receives plates one at a time until it holds
    `expected_plates` (default 1)
  - a full bay is cleared shortly after a claim appears for it, or after
    `unclaimed_pickup_s` with no claim (exercises the "unclaimed" path)
  - ingredient zones get random picks attributed via the active-ticket context,
    with an occasional INGREDIENT_CHANGE_PENDING
  - CAMERA_STATUS heartbeats every 5 s; ZONE_SNAPSHOT / BAY_STATE periodically

`/mock/*` endpoints (see api.py) can force an obstruction or a specific plate move.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field

from cvsvc.config import CVConfig
from cvsvc.context import ContextStore
from cvsvc.emitter import Emitter
from cvsvc.events import EventBus

log = logging.getLogger(__name__)


@dataclass
class _Bay:
    count: int = 0
    last_change: float = 0.0
    full_since: float | None = None
    claim_seen_at: float | None = None
    last_assignment: tuple | None = None


@dataclass
class _Zone:
    ingredient: str
    count: int
    max_count: int


@dataclass
class MockKitchen:
    cfg: CVConfig
    bus: EventBus
    context: ContextStore
    emitter: Emitter
    plate_interval_s: float = 4.0
    pickup_after_claim_s: float = 3.0
    unclaimed_pickup_s: float = 25.0
    pick_every_s: float = 8.0
    pending_probability: float = 0.1
    seed: int | None = None
    tick_s: float = 0.25
    bays: dict[str, _Bay] = field(default_factory=dict)
    zones: dict[str, _Zone] = field(default_factory=dict)
    camera_state: dict[str, tuple[str, str | None, float]] = field(default_factory=dict)
    auto_plating: bool = True
    auto_ingredients: bool = True

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        bay_ids = [b.id for b in self.cfg.plating.bays] or ["A", "B", "C"]
        self.bays = {b: _Bay() for b in bay_ids}
        if self.cfg.ingredient.zones:
            self.zones = {z.id: _Zone(z.ingredient, z.max_count, z.max_count) for z in self.cfg.ingredient.zones}
        else:
            self.zones = {"Z1": _Zone("tomato_slice", 8, 8), "Z2": _Zone("cheese_slice", 6, 6)}
        now = time.time()
        self.camera_state = {
            self.emitter.ingredient_camera: ("ok", None, now),
            self.emitter.plating_camera: ("ok", None, now),
        }

    # ---- helpers ----
    def _cam_ok(self, cam: str) -> bool:
        return self.camera_state[cam][0] in ("ok", "degraded")

    async def _pub(self, ev) -> None:
        await self.bus.publish(ev)

    async def set_camera_state(self, cam: str, state: str, reason: str | None = None) -> None:
        prev = self.camera_state.get(cam, ("ok", None, 0))[0]
        now = time.time()
        self.camera_state[cam] = (state, reason, now)
        await self._pub(self.emitter.camera_status(cam, state, reason, now))
        if prev in ("obstructed", "lost") and state == "ok" and cam == self.emitter.plating_camera:
            for bay_id, b in self.bays.items():
                await self._pub(self.emitter.bay_state(bay_id, b.count, note="post_obstruction_recount"))

    async def move_plates(self, bay_id: str, delta: int) -> None:
        """Force plates in (+) or out (-) of a bay. Ignored while the plating camera is obstructed."""
        if not self._cam_ok(self.emitter.plating_camera):
            b = self.bays[bay_id]
            b.count = max(0, b.count + delta)  # the world changes; the camera just doesn't see it
            return
        await self._change_bay(bay_id, self.bays[bay_id].count + delta)

    async def _change_bay(self, bay_id: str, new: int) -> None:
        b = self.bays[bay_id]
        new = max(0, min(new, self.cfg.plating.max_plates_per_bay))
        if new == b.count:
            return
        before, b.count, b.last_change = b.count, new, time.time()
        conf = round(self.rng.uniform(0.85, 0.99), 2)
        if new > before:
            await self._pub(self.emitter.plate_arrived(bay_id, before, new, conf))
        else:
            await self._pub(self.emitter.plate_removed(bay_id, before, new, conf))
        await self._pub(self.emitter.bay_state(bay_id, new, conf))

    async def resolve_zone(self, zone_id: str, count: int) -> None:
        z = self.zones[zone_id]
        z.count = count
        z.max_count = max(z.max_count, count)
        await self._pub(self.emitter.zone_snapshot(zone_id, z.ingredient, count))

    def zone_counts(self) -> dict[str, int]:
        return {k: z.count for k, z in self.zones.items()}

    # ---- loop ----
    async def run(self) -> None:
        log.info("mock kitchen running: bays=%s zones=%s", list(self.bays), list(self.zones))
        for zid, z in self.zones.items():
            await self._pub(self.emitter.zone_snapshot(zid, z.ingredient, z.count))
        for bay_id, b in self.bays.items():
            await self._pub(self.emitter.bay_state(bay_id, b.count))
        last_hb = last_snap = last_pick = time.time()
        while True:
            now = time.time()
            if now - last_hb >= self.cfg.health.heartbeat_s:
                last_hb = now
                for cam, (state, reason, since) in self.camera_state.items():
                    await self._pub(self.emitter.camera_status(cam, state, reason, since, heartbeat=True))
            if self.auto_plating and self._cam_ok(self.emitter.plating_camera):
                await self._tick_plating(now)
            if self._cam_ok(self.emitter.ingredient_camera):
                if self.auto_ingredients and now - last_pick >= self.pick_every_s:
                    last_pick = now
                    await self._random_pick(now)
            if now - last_snap >= min(self.cfg.ingredient.snapshot_interval_s, self.cfg.plating.snapshot_interval_s):
                last_snap = now
                if self._cam_ok(self.emitter.ingredient_camera):
                    for zid, z in self.zones.items():
                        await self._pub(self.emitter.zone_snapshot(zid, z.ingredient, z.count))
                if self._cam_ok(self.emitter.plating_camera):
                    for bay_id, b in self.bays.items():
                        await self._pub(self.emitter.bay_state(bay_id, b.count))
            await asyncio.sleep(self.tick_s)

    async def _tick_plating(self, now: float) -> None:
        for bay_id, b in self.bays.items():
            a = self.context.bay(bay_id)
            key = (a.ticket_id, a.table, a.course, a.expected_plates) if a else None
            if key != b.last_assignment:
                b.last_assignment = key
                b.full_since = b.claim_seen_at = None
                b.last_change = now
                await self._pub(self.emitter.bay_state(bay_id, b.count))  # label shows within one tick
            if a is not None:
                expected = a.expected_plates or 1
                if b.count < expected and now - b.last_change >= self.plate_interval_s:
                    await self._change_bay(bay_id, b.count + 1)
                    continue
                if b.count >= expected and b.count > 0:
                    b.full_since = b.full_since or now
                    claim = self.context.claim(bay_id)
                    if claim is not None:
                        b.claim_seen_at = b.claim_seen_at or now
                        if now - b.claim_seen_at >= self.pickup_after_claim_s:
                            await self._change_bay(bay_id, 0)
                    else:
                        b.claim_seen_at = None
                        if now - b.full_since >= self.unclaimed_pickup_s:
                            await self._change_bay(bay_id, 0)

    async def _random_pick(self, now: float) -> None:
        candidates = [zid for zid, z in self.zones.items() if z.count > 0]
        if not candidates:
            return
        zid = self.rng.choice(candidates)
        z = self.zones[zid]
        attr = self.context.attribution()
        if self.rng.random() < self.pending_probability:
            est = max(0, z.count - self.rng.randint(1, 2))
            await self._pub(self.emitter.pending(zid, z.ingredient, "unstable_count", z.count, est, 0.5, attr))
            return  # baseline unchanged until staff resolve it
        n = min(z.count, self.rng.choice([1, 1, 2]))
        before = z.count
        z.count -= n
        await self._pub(self.emitter.picked(zid, z.ingredient, before, z.count,
                                            self.rng.uniform(0.8, 0.98), attr))
