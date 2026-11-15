"""Team CV observations -> canonical v2 commands, never a second Kitchen store.

The owning CV event schema is loaded from cv-service/cvsvc/events.py unchanged.
Only producer-captured unit bindings and measured stable/no-motion evidence can
advance plating. Legacy ticket/bay counts and ingredient trips cannot do so.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    TypeAdapter,
)

from app.coordination.rules import require
from app.mvp.contracts import Command


@lru_cache(maxsize=1)
def producer_contract():
    candidates = [
        Path(__file__).resolve().parents[3] / "cv-service/cvsvc/events.py",
        Path(__file__).resolve().parents[2] / "cvsvc/events.py",
    ]
    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location(
                "dig_in_cv_event_contract", path
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module.EventAdapter
    raise RuntimeError(
        "Owning cv-service/cvsvc/events.py is missing from the application package"
    )


class CaptureBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    zone_id: str
    assignment_version: int = Field(ge=0)
    order_id: str | None
    dish_id: str | None


class CaptureEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stable_ms: int = Field(ge=0, le=60000)
    hand_present: StrictBool


class CVEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: dict
    run_id: str = Field(min_length=1, max_length=100)
    simulated: StrictBool
    binding: CaptureBinding | None = None
    evidence: CaptureEvidence | None = None


class CVBridge:
    """Process-local bridge receipts and feed health; Core owns accepted state.

    Receipts cover the complete producer envelope, not merely its translated
    command. Watchdog loss uses Core camera_status so unknown never frees zones.
    """

    CAMERA_MAP = {
        "plating_cam": "plating-cam",
        "ingredient_cam": "ingredient-cam",
        "plating-cam": "plating-cam",
        "ingredient-cam": "ingredient-cam",
    }

    def __init__(
        self,
        restaurant: Callable,
        *,
        clock=time.monotonic,
        now=lambda: datetime.now(UTC),
        stale_after_s=10.0,
    ):
        self.restaurant = restaurant
        self.clock, self.now, self.stale_after_s = clock, now, stale_after_s
        self.lock = threading.RLock()
        self.receipts = {}
        self.feeds = {}

    def _authorize(self, session):
        core = self.restaurant()
        require(session in core.sessions, "Select a demo staff/device session")
        actor = core.state.actors[core.sessions[session]]
        require(actor.role in ("cook", "lead"), "Kitchen/lead CV session required")
        return actor

    def context(self, session):
        core = self.restaurant()
        with core.lock:
            self._authorize(session)
            return {
                "schema_version": 2,
                "stable_ms_required": core.state.stable_ms_required,
                "camera_map": self.CAMERA_MAP,
                "zones": {
                    key: {
                        "zone_id": zone.id,
                        "reconciliation_id": next(
                            (
                                event.event_id
                                for event in reversed(core.state.events)
                                if (
                                    event.type == "zone.reconciled"
                                    or (
                                        event.type == "dish.picked_up"
                                        and event.source == "tap"
                                    )
                                )
                                and event.payload.get("zone_id") == zone.id
                            ),
                            None,
                        ),
                        "assignment_version": zone.assignment_version,
                        "order_id": zone.order_id,
                        "dish_id": zone.dish_id,
                        "camera_id": zone.camera_id,
                        "table_id": core.state.orders[zone.order_id].table_id
                        if zone.order_id
                        else None,
                    }
                    for key, zone in core.state.zones.items()
                },
            }

    def receive(self, body: CVEnvelope, session):
        core = self.restaurant()
        with self.lock, core.lock:
            actor = self._authorize(session)
            event = producer_contract().validate_python(body.event)
            at = (
                TypeAdapter(AwareDatetime)
                .validate_python(event.observed_at)
                .astimezone(UTC)
            )
            fingerprint = hashlib.sha256(
                (
                    actor.id + json.dumps(body.model_dump(mode="json"), sort_keys=True)
                ).encode()
            ).hexdigest()
            if event.event_id in self.receipts:
                old, result = self.receipts[event.event_id]
                require(
                    old == fingerprint,
                    "CV event_id reused with different evidence/identity",
                )
                return {**result, "replayed": True}
            age = (self.now() - at).total_seconds()
            require(
                -5 <= age <= self.stale_after_s,
                "Stale or future CV observation timestamp",
            )
            require(event.camera_id in self.CAMERA_MAP, "Unknown producer camera")
            camera_id = self.CAMERA_MAP[event.camera_id]
            require(camera_id in core.state.cameras, "Unknown canonical camera")
            expected_source = (
                "cv.plating" if camera_id == "plating-cam" else "cv.ingredient"
            )
            require(event.source == expected_source, "CV source/camera mismatch")
            if event.type == "CAMERA_STATUS":
                previous = self.feeds.get(camera_id)
                require(
                    previous is None or at >= previous["source_time"],
                    "Out-of-order camera health",
                )
                status = {
                    "ok": "ok",
                    "degraded": "blocked",
                    "obstructed": "blocked",
                    "lost": "offline",
                }[event.payload.state]
                payload = {
                    "action": "camera_status",
                    "camera_id": camera_id,
                    "status": status,
                    "reason": f"CV {event.payload.state}",
                }
            elif event.type in ("PLATE_ARRIVED", "PLATE_REMOVED", "BAY_STATE"):
                require(
                    event.confidence >= 0.7, "Low-confidence occupancy requires review"
                )
                require(
                    camera_id == "plating-cam",
                    "Plate observation must use plating camera",
                )
                require(
                    body.binding is not None and body.evidence is not None,
                    "Capture-time unit binding and measured stable/no-hand evidence required",
                )
                binding = body.binding
                require(
                    event.bay_id == binding.zone_id
                    and binding.zone_id in core.state.zones,
                    "Producer bay must map one-to-one to canonical physical zone",
                )
                zone = core.state.zones[binding.zone_id]
                require(
                    zone.camera_id == camera_id
                    and zone.assignment_version == binding.assignment_version
                    and zone.order_id == binding.order_id
                    and zone.dish_id == binding.dish_id,
                    "Stale or mismatched capture-time unit assignment",
                )
                require(
                    not event.attribution.ambiguous
                    and event.attribution.ticket_id == binding.order_id,
                    "Producer attribution does not match captured order",
                )
                count = (
                    event.payload.plate_count
                    if event.type == "BAY_STATE"
                    else event.payload.count_after
                )
                require(
                    count in (0, 1),
                    "Multi-plate bay requires review; v2 allows one physical unit per zone",
                )
                require(
                    event.status == "observed",
                    "Pending evidence cannot establish occupancy",
                )
                if event.type == "BAY_STATE":
                    require(
                        event.payload.occupied == (count == 1),
                        "Inconsistent occupied/count evidence",
                    )
                    require(
                        event.payload.assigned_ticket_id == binding.order_id,
                        "Bay state assignment does not match captured order",
                    )
                    require(
                        event.payload.note is None,
                        "Recovery/recount evidence requires staff review",
                    )
                payload = {
                    "action": "zone_observation",
                    "zone_id": binding.zone_id,
                    "assignment_version": binding.assignment_version,
                    "occupied": bool(count),
                    **body.evidence.model_dump(),
                }
            else:
                # A reach/trip is not a countable stock delta; a reported count
                # is not an accepted inventory movement. Keep original CV logs
                # for review without silently activating recipe deductions.
                result = {
                    "event_id": event.event_id,
                    "outcome": "review_required",
                    "reason": "Ingredient evidence needs countable v2 review; no stock deducted",
                    "replayed": False,
                }
                self.receipts[event.event_id] = (fingerprint, result)
                return result
            command = Command(
                event_id=event.event_id,
                source="system" if event.type == "CAMERA_STATUS" else "camera",
                time=at,
                device_id=camera_id,
                run_id=body.run_id,
                simulated=body.simulated,
                payload=payload,
            )
            accepted = core.execute(command, session)
            result = {
                "event_id": event.event_id,
                "result": accepted["result"],
                "replayed": accepted["replayed"],
            }
            self.receipts[event.event_id] = (fingerprint, result)
            if event.type == "CAMERA_STATUS":
                self.feeds[camera_id] = {
                    "last_seen": self.clock(),
                    "source_time": at,
                    "session": session,
                    "event_id": event.event_id,
                    "simulated": body.simulated,
                    "run_id": body.run_id,
                    "expired": False,
                }
            return result

    def expire(self):
        core = self.restaurant()
        with self.lock:
            for camera_id, feed in self.feeds.items():
                if (
                    feed["expired"]
                    or self.clock() - feed["last_seen"] <= self.stale_after_s
                ):
                    continue
                command = Command(
                    event_id=f"cv-expired:{camera_id}:{hashlib.sha256(feed['event_id'].encode()).hexdigest()[:24]}",
                    source="system",
                    time=self.now(),
                    device_id=camera_id,
                    simulated=feed["simulated"],
                    run_id=feed["run_id"],
                    payload={
                        "action": "camera_status",
                        "camera_id": camera_id,
                        "status": "offline",
                        "reason": "CV heartbeat expired; occupancy is unknown",
                    },
                )
                core.execute(command, feed["session"])
                feed["expired"] = True
