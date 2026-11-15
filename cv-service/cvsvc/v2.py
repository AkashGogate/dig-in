"""Opt-in CV -> canonical v2 runner. Default mock; --camera opens configured feeds.

No separate kitchen-backend, raw-MJPEG server, claims or recipe trip deduction.
Actual camera processing reuses the teammate's pipeline and calibrated counters.
A sidecar samples measured count/motion under capture-time canonical bindings.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import logging
import os
import threading
import time
from collections import deque

import httpx

from cvsvc.config import load_config
from cvsvc.events import Attribution, BayState, BayStatePayload, EventIds, utcnow_iso
from cvsvc.main import build_runtime

log = logging.getLogger(__name__)


class EvidenceSampler:
    """Strict one-zone/one-unit proof. Motion/health/context changes restart dwell."""

    def __init__(self, publish, run_id, simulated, *, clock=time.monotonic):
        self.publish, self.run_id, self.simulated = publish, run_id, simulated
        self.clock = clock
        self.ids = EventIds(run_id)
        self.lock = threading.RLock()
        self.context = None
        self.context_at = 0.0
        self.candidates = {}
        self.quarantined = {}
        self.history = {}
        self.await_empty = set()

    def set_context(self, context):
        with self.lock:
            self.context, self.context_at = copy.deepcopy(context), self.clock()

    def reset(self):
        with self.lock:
            self.candidates.clear()

    def quarantine(self, bay_id=None):
        with self.lock:
            for key, binding in (self.context or {}).get("zones", {}).items():
                if bay_id is None or key == bay_id:
                    self.quarantined[key] = binding.get("reconciliation_id")
            self.candidates.clear()

    def sample(self, bay_id, ts, count, hand_present, camera_state, confidence=1.0):
        with self.lock:
            mono = self.clock()
            if self.context is None or mono - self.context_at > 3:
                self.candidates.pop(bay_id, None)
                return
            binding = self.context["zones"].get(bay_id)
            if binding is None:
                return
            if bay_id in self.quarantined:
                if binding.get("reconciliation_id") == self.quarantined[bay_id]:
                    self.candidates.pop(bay_id, None)
                    return
                del self.quarantined[bay_id]
            token = (
                binding["assignment_version"],
                binding["order_id"],
                binding["dish_id"],
            )
            prior = self.history.get(bay_id)
            if prior and prior[0] != token and prior[1] != 0:
                self.await_empty.add(bay_id)
            if hand_present or camera_state != "ok" or confidence < 0.7:
                self.candidates.pop(bay_id, None)
                return
            previous = self.candidates.get(bay_id)
            if (
                previous is None
                or previous["token"] != token
                or previous["count"] != count
                or mono - previous["last"] > 0.35
                or ts < previous["last_ts"]
            ):
                self.candidates[bay_id] = {
                    "token": token,
                    "count": count,
                    "since": mono,
                    "last": mono,
                    "last_ts": ts,
                    "confidence": confidence,
                    "emitted": False,
                }
                return
            previous["last"], previous["last_ts"] = mono, ts
            previous["confidence"] = min(previous["confidence"], confidence)
            stable_ms = int((mono - previous["since"]) * 1000)
            if previous["emitted"] or stable_ms < self.context["stable_ms_required"]:
                return
            if bay_id in self.await_empty:
                if count != 0:
                    return
                self.await_empty.remove(bay_id)
            self.history[bay_id] = (token, count)
            previous["emitted"] = True
            event = BayState(
                event_id=self.ids.next("plating_cam", bay_id, "v2_evidence"),
                source="cv.plating",
                camera_id="plating_cam",
                observed_at=utcnow_iso(ts),
                bay_id=bay_id,
                confidence=previous["confidence"],
                attribution=Attribution(
                    ticket_id=binding["order_id"],
                    method="bay_assignment" if binding["order_id"] else "none",
                ),
                payload=BayStatePayload(
                    plate_count=count,
                    occupied=count > 0,
                    assigned_ticket_id=binding["order_id"],
                    assigned_table=binding.get("table_id"),
                    assigned_course=None,
                    expected_plates=1 if binding["dish_id"] else None,
                ),
            )
            self.publish(
                {
                    "event": event.model_dump(mode="json"),
                    "run_id": self.run_id,
                    "simulated": self.simulated,
                    "binding": {
                        k: binding[k]
                        for k in (
                            "zone_id",
                            "assignment_version",
                            "order_id",
                            "dish_id",
                        )
                    },
                    "evidence": {
                        "stable_ms": min(stable_ms, 60000),
                        "hand_present": False,
                    },
                }
            )


class CanonicalClient:
    """Individual exact-envelope retries; a terminal rejection never drops peers.

    Assignment evidence is frozen before queueing, never filled from current
    context during delivery/retry. Both HTTPBasic variables must be supplied or
    both absent. Secrets are not printed or placed in request URLs.
    """

    def __init__(self, base_url, runtime, simulated):
        user, password = (
            os.environ.get("DEMO_AUTH_USER"),
            os.environ.get("DEMO_AUTH_PASS"),
        )
        if bool(user) != bool(password):
            raise ValueError("Set both DEMO_AUTH_USER and DEMO_AUTH_PASS or neither")
        self.http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=10,
            auth=httpx.BasicAuth(user, password) if user else None,
        )
        self.runtime, self.simulated = runtime, simulated
        self.session = None
        self.loop = None
        self.queue = asyncio.Queue(maxsize=1000)
        self.reviews = deque(maxlen=100)
        self.sampler = EvidenceSampler(self.enqueue, runtime.bus.ids.boot_id, simulated)

    def enqueue(self, envelope):
        frozen = copy.deepcopy(envelope)

        def put():
            try:
                self.queue.put_nowait(frozen)
            except asyncio.QueueFull:
                self.reviews.append(
                    {
                        "event_id": frozen["event"]["event_id"],
                        "reason": "local_queue_full",
                    }
                )
                log.error(
                    "CV v2 queue full; evidence withheld, manual recovery required"
                )

        if self.loop is not None:
            self.loop.call_soon_threadsafe(put)

    def health_event(self, event):
        if (
            event["type"] == "BAY_STATE"
            and event["payload"].get("note") == "post_obstruction_recount"
        ):
            self.sampler.quarantine(event["bay_id"])
        if event["type"] != "CAMERA_STATUS":
            return
        if event["payload"]["state"] != "ok":
            self.sampler.quarantine()
        self.enqueue(
            {
                "event": event,
                "run_id": self.runtime.bus.ids.boot_id,
                "simulated": self.simulated,
            }
        )

    async def enter_session(self):
        response = await self.http.post("/api/v2/sessions", json={"actor_id": "cook-1"})
        response.raise_for_status()
        self.session = response.json()["session_id"]

    def headers(self):
        return {"X-Demo-Session": self.session or ""}

    async def contexts(self):
        while True:
            try:
                if self.session is None:
                    await self.enter_session()
                response = await self.http.get(
                    "/api/v2/cv/context", headers=self.headers()
                )
                if response.status_code == 409:
                    self.session = None
                response.raise_for_status()
                context = response.json()
                covered = {bay.id for bay in self.runtime.cfg.plating.bays}
                expected = {
                    key
                    for key, zone in context["zones"].items()
                    if zone["camera_id"] == "plating-cam"
                }
                if covered != expected:
                    raise ValueError(
                        "Calibrated CV bays must cover exactly the canonical plating zones"
                    )
                self.sampler.set_context(context)
            except (httpx.HTTPError, KeyError, ValueError):
                self.sampler.reset()
                log.warning("Canonical context unavailable; CV readiness withheld")
            await asyncio.sleep(1)

    async def deliver(self):
        while True:
            envelope = await self.queue.get()
            while True:
                try:
                    if self.session is None:
                        await self.enter_session()
                    response = await self.http.post(
                        "/api/v2/cv/observations", json=envelope, headers=self.headers()
                    )
                    if response.is_success:
                        break
                    if response.status_code == 409 and "Select a demo" in response.text:
                        self.session = None
                        continue
                    if response.status_code in (400, 409, 422):
                        self.reviews.append(
                            {
                                "event_id": envelope["event"]["event_id"],
                                "status": response.status_code,
                            }
                        )
                        log.warning(
                            "CV observation requires review (HTTP %s); unrelated queue entries preserved",
                            response.status_code,
                        )
                        break
                    response.raise_for_status()
                except httpx.HTTPError:
                    log.warning(
                        "CV delivery unavailable; retaining exact envelope in memory"
                    )
                await asyncio.sleep(1)
            self.queue.task_done()

    async def mock_samples(self):
        while True:
            now = time.time()
            for bay_id, bay in self.runtime.mock.bays.items():
                state = self.runtime.mock.camera_state[self.runtime.cfg.plating.camera][
                    0
                ]
                self.sampler.sample(bay_id, now, bay.count, False, state)
            await asyncio.sleep(0.1)

    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.runtime.bus.listeners.append(self.health_event)
        jobs = [
            asyncio.create_task(self.contexts()),
            asyncio.create_task(self.deliver()),
        ]
        if self.simulated:
            jobs.append(asyncio.create_task(self.mock_samples()))
        try:
            await asyncio.Event().wait()
        finally:
            for task in jobs:
                task.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
            await self.http.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--config", default="config/v2.yaml")
    parser.add_argument(
        "--camera",
        action="store_true",
        help="Explicitly open configured cameras; default is mock",
    )
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    cfg = load_config(args.config)
    # Canonical delivery owns its sink. Do not also POST legacy batched events
    # into the old independent kitchen service or a second operational backend.
    cfg.sinks.backend_url = None
    if args.camera:
        from pathlib import Path

        from cvsvc.ingredient.hands import HandDetector

        # Hardware mode cannot silently substitute motion for hand absence, or
        # a first scene for a human-captured empty calibration reference.
        for camera_id in cfg.cameras:
            if not (Path(cfg.calibration_dir) / f"{camera_id}.png").is_file():
                raise ValueError("Calibrate empty references before --camera")
        hand_detector = HandDetector(cfg.ingredient.hand_model_path)
    rt = build_runtime(
        cfg,
        mock=not args.camera,
        backend_url="",
        mock_auto=False,
        legacy_delivery=False,
    )
    client = CanonicalClient(args.backend, rt, simulated=not args.camera)
    if args.camera:
        pipelines = rt.pipeline
        pipelines.v2_sampler = client.sampler.sample
        pipelines.v2_require_reference = True
        pipelines.v2_hand_detector = hand_detector
        rt.background = [pipelines.run]
        rt.resolve_zone = pipelines.resolve_zone
        rt.capture_reference = pipelines.capture_reference
        rt.mjpeg = None  # no raw/overlay streaming in the canonical runner
        rt.health = pipelines.health
    rt.background.insert(0, client.run)
    import uvicorn

    from cvsvc.api import create_app

    uvicorn.run(create_app(rt), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
