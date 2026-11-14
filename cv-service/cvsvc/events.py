"""Event contract (CV_SPEC.md section 4) + EventBus.

This module is the single definition of the CV -> backend contract. Run
`python -m cvsvc.events` to regenerate ../schema/events.schema.json.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

log = logging.getLogger(__name__)

Status = Literal["observed", "pending_review"]
Source = Literal["cv.ingredient", "cv.plating"]
CameraState = Literal["ok", "degraded", "obstructed", "lost"]
PendingReason = Literal[
    "unstable_count", "occlusion_timeout", "unexpected_increase", "large_delta", "post_obstruction_mismatch"
]


def utcnow_iso(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(ts if ts is not None else time.time(), tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


class Attribution(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)
    ticket_id: str | None = None
    method: Literal["active_ticket_context", "bay_assignment", "none"] = "none"
    ambiguous: bool = False


# ---- payloads -------------------------------------------------------------

class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class IngredientPickedPayload(_Payload):
    ingredient: str
    qty_delta: int = Field(lt=0)
    count_before: int
    count_after: int
    unit: Literal["portion"] = "portion"


class IngredientReturnedPayload(_Payload):
    ingredient: str
    qty_delta: int = Field(gt=0)
    count_before: int
    count_after: int


class IngredientChangePendingPayload(_Payload):
    ingredient: str
    reason: PendingReason
    count_before: int
    count_after_estimate: int | None


class ZoneSnapshotPayload(_Payload):
    ingredient: str
    count: int


class PlateArrivedPayload(_Payload):
    count_before: int
    count_after: int
    delta: int = Field(gt=0)
    expected_plates: int | None
    count_matches_expected: bool | None


class PlateRemovedPayload(_Payload):
    count_before: int
    count_after: int
    delta: int = Field(gt=0)
    bay_now_empty: bool
    claimed_task_id: str | None
    claimed_by: str | None
    unclaimed: bool


class BayStatePayload(_Payload):
    plate_count: int
    occupied: bool
    assigned_ticket_id: str | None
    assigned_table: str | None
    assigned_course: str | None
    # carried through from context for display only (CV_SPEC 5); CV never uses it to decide anything
    expected_plates: int | None = None
    # optional note, e.g. "post_obstruction_recount"
    note: str | None = None


class CameraStatusPayload(_Payload):
    state: CameraState
    reason: str | None
    since: str
    heartbeat: bool = False


# ---- events ---------------------------------------------------------------

class _EventBase(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)
    event_id: str
    source: Source
    camera_id: str
    observed_at: str
    zone_id: str | None = None
    bay_id: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: Status = "observed"
    attribution: Attribution = Field(default_factory=Attribution)


class IngredientPicked(_EventBase):
    type: Literal["INGREDIENT_PICKED"] = "INGREDIENT_PICKED"
    payload: IngredientPickedPayload


class IngredientReturned(_EventBase):
    type: Literal["INGREDIENT_RETURNED"] = "INGREDIENT_RETURNED"
    payload: IngredientReturnedPayload


class IngredientChangePending(_EventBase):
    type: Literal["INGREDIENT_CHANGE_PENDING"] = "INGREDIENT_CHANGE_PENDING"
    status: Literal["pending_review"] = "pending_review"
    payload: IngredientChangePendingPayload


class ZoneSnapshot(_EventBase):
    type: Literal["ZONE_SNAPSHOT"] = "ZONE_SNAPSHOT"
    payload: ZoneSnapshotPayload


class PlateArrived(_EventBase):
    type: Literal["PLATE_ARRIVED"] = "PLATE_ARRIVED"
    payload: PlateArrivedPayload


class PlateRemoved(_EventBase):
    type: Literal["PLATE_REMOVED"] = "PLATE_REMOVED"
    payload: PlateRemovedPayload


class BayState(_EventBase):
    type: Literal["BAY_STATE"] = "BAY_STATE"
    payload: BayStatePayload


class CameraStatus(_EventBase):
    type: Literal["CAMERA_STATUS"] = "CAMERA_STATUS"
    payload: CameraStatusPayload


Event = Annotated[
    Union[
        IngredientPicked,
        IngredientReturned,
        IngredientChangePending,
        ZoneSnapshot,
        PlateArrived,
        PlateRemoved,
        BayState,
        CameraStatus,
    ],
    Field(discriminator="type"),
]
EventAdapter: TypeAdapter[Event] = TypeAdapter(Event)

PLATE_TYPES = {"PLATE_ARRIVED", "PLATE_REMOVED", "BAY_STATE"}
INGREDIENT_TYPES = {"INGREDIENT_PICKED", "INGREDIENT_RETURNED", "INGREDIENT_CHANGE_PENDING", "ZONE_SNAPSHOT"}


# ---- deterministic ids ----------------------------------------------------

_NS = uuid.UUID("6f1c3c1e-2b0e-4d8a-9a5e-6b7f2c1d0e9a")


class EventIds:
    """Deterministic event ids: uuid5(boot_id, camera, zone/bay, type, counter).

    The counter increments once per physical change per (camera, target), so an
    event retried from the outbox keeps the same id and the backend dedups it.
    boot_id separates service runs so counters restarting at 0 never collide
    with ids from a previous run.
    """

    def __init__(self, boot_id: str | None = None) -> None:
        self.boot_id = boot_id or uuid.uuid4().hex
        self._counters: dict[tuple[str, str], int] = {}

    def next(self, camera_id: str, target: str | None, kind: str) -> str:
        key = (camera_id, target or "-")
        n = self._counters.get(key, 0) + 1
        self._counters[key] = n
        return str(uuid.uuid5(_NS, f"{self.boot_id}:{camera_id}:{target or '-'}:{kind}:{n}"))


# ---- bus ------------------------------------------------------------------

class Sink(Protocol):
    async def send(self, event: dict[str, Any]) -> None: ...


class EventBus:
    """Fan-out of events to sinks. Thread-safe `publish_threadsafe` for camera loops."""

    def __init__(self, ids: EventIds | None = None, recent: int = 500) -> None:
        self.ids = ids or EventIds()
        self.sinks: list[Sink] = []
        self.recent: deque[dict[str, Any]] = deque(maxlen=recent)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[dict[str, Any]] | None = None
        self.listeners: list[Any] = []  # sync callables(event_dict), e.g. state snapshots

    def add_sink(self, sink: Sink) -> None:
        self.sinks.append(sink)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        assert self._queue is not None
        while True:
            ev = await self._queue.get()
            for sink in self.sinks:
                try:
                    await sink.send(ev)
                except Exception:  # a broken sink must never stop the bus
                    log.exception("sink %r failed", sink)

    def _accept(self, event: BaseModel | dict[str, Any]) -> dict[str, Any]:
        if isinstance(event, BaseModel):
            data = event.model_dump(mode="json")
        else:
            data = EventAdapter.validate_python(event).model_dump(mode="json")
        self.recent.append(data)
        for fn in self.listeners:
            try:
                fn(data)
            except Exception:
                log.exception("listener failed")
        return data

    async def publish(self, event: BaseModel | dict[str, Any]) -> dict[str, Any]:
        data = self._accept(event)
        if self._queue is not None:
            await self._queue.put(data)
        return data

    def publish_threadsafe(self, event: BaseModel | dict[str, Any]) -> None:
        if self._loop is None:
            raise RuntimeError("EventBus not started")
        self._loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.publish(event)))


def write_schema(path: str | Path) -> None:
    schema = EventAdapter.json_schema(mode="serialization")  # every field the CV emits is required
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "dig-in CV event"
    schema["description"] = "CV -> backend observation event. Generated from cv-service/cvsvc/events.py; do not edit by hand."
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(schema, indent=2) + "\n")


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[2] / "schema" / "events.schema.json"
    write_schema(out)
    print(f"wrote {out}")
