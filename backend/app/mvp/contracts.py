"""MVP v2 authority. v1 coordination/task contracts remain explicitly legacy.

MenuDocument and CanonicalEvent are owned by their lanes and imported here,
not independently redefined by UI, voice, CV or analytics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.analytics.events import CanonicalEvent
from app.mvp.menu import MenuDocument


def now():
    return datetime.now(UTC)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Actor(Model):
    id: str
    name: str
    role: Literal["server", "cook", "lead"]


class Table(Model):
    id: str
    seats: list[int] = [1, 2, 3, 4]


class LineInput(Model):
    id: str = Field(min_length=1, max_length=100)
    menu_id: str
    quantity: int = Field(ge=1, le=12)
    modifiers: list[str] = Field(default_factory=list)
    seat: int | None = None
    requests: str = Field(default="", max_length=500)


class Line(LineInput):
    item_name: str
    station: str | None = None
    typical_minutes: float | None = None
    recipe: list[dict] | None = None
    price_cents: int | None = None


class DraftFlag(Model):
    id: str
    code: str
    message: str
    candidates: list[str] = Field(default_factory=list)
    spoken_table_id: str | None = None


class Order(Model):
    id: str
    owner: str
    table_id: str
    revision: int = 1
    status: Literal[
        "draft",
        "submitted",
        "acknowledged",
        "cooking",
        "ready",
        "picked_up",
        "delivered",
    ] = "draft"
    lines: list[Line] = Field(default_factory=list)
    flags: list[DraftFlag] = Field(default_factory=list)
    voice_baseline: list[Line] | None = None
    capture_mode: Literal["manual", "mock_voice", "live_voice"] = "manual"
    dietary_check: Literal["not_asked", "none_reported", "requests_recorded"] = (
        "not_asked"
    )
    corrected_draft_lines: int = 0
    initial_voice_draft_line_count: int = 0
    zone_status: Literal["unassigned", "waiting", "assigned", "released"] = "unassigned"
    ready_notified: bool = False
    created_at: AwareDatetime = Field(default_factory=now)
    submitted_at: AwareDatetime | None = None
    acknowledged_at: AwareDatetime | None = None
    ready_at: AwareDatetime | None = None
    picked_up_at: AwareDatetime | None = None
    delivered_at: AwareDatetime | None = None
    waiting_since: AwareDatetime | None = None


class Dish(Model):
    id: str
    order_id: str
    line_id: str
    menu_id: str
    item_name: str
    modifiers: list[str]
    seat: int | None = None
    requests: str = ""
    station: str | None = None
    typical_minutes: float | None = None
    stage: Literal["queued", "started", "ready", "picked_up"] = "queued"
    zone_id: str | None = None
    started_at: AwareDatetime | None = None
    ready_at: AwareDatetime | None = None
    picked_up_at: AwareDatetime | None = None


class PlatingZone(Model):
    id: str
    camera_id: str = "plating-cam"
    rectangle: tuple[int, int, int, int]
    assignment_version: int = 0
    order_id: str | None = None
    dish_id: str | None = None
    occupancy: Literal["empty", "occupied", "unknown"] = "empty"
    needs_review: bool = False
    blocked_reason: str | None = None
    had_stable_occupancy: bool = False
    last_signal_at: AwareDatetime | None = None
    verified_by: Literal["fixture", "tap", "camera", "unknown"] = "fixture"


class Camera(Model):
    id: str
    status: Literal["ok", "blocked", "offline"] = "ok"
    mode: Literal["mock", "adapter"] = "mock"
    reason: str = "Simulated feed; no image processing connected"


class IngredientZone(Model):
    id: str
    ingredient: str
    initial: int = Field(ge=0)
    unit: str = "portion"


class StockMovement(Model):
    event_id: str
    zone_id: str
    delta: int
    kind: Literal["consume", "return", "restock", "waste", "correction"]
    observation_id: str | None = None
    order_id: str | None = None
    reason: str


class Notification(Model):
    id: str
    type: Literal["order.ready"] = "order.ready"
    order_id: str
    table_id: str
    time: AwareDatetime


class State(Model):
    schema_version: Literal[2] = 2
    actors: dict[str, Actor]
    tables: dict[str, Table]
    menu: MenuDocument
    orders: dict[str, Order] = Field(default_factory=dict)
    dishes: dict[str, Dish] = Field(default_factory=dict)
    zones: dict[str, PlatingZone]
    cameras: dict[str, Camera]
    ingredient_zones: dict[str, IngredientZone]
    stock_movements: list[StockMovement] = Field(default_factory=list)
    stock_observations: dict[str, dict] = Field(default_factory=dict)
    notifications: list[Notification] = Field(default_factory=list)
    events: list[CanonicalEvent] = Field(default_factory=list)
    stable_ms_required: int = Field(default=1500, ge=1000, le=2000)


class StartOrder(Model):
    action: Literal["start_order"]
    table_id: str


class EditDraft(Model):
    action: Literal["edit_draft"]
    order_id: str
    revision: int
    table_id: str
    lines: list[LineInput] = Field(max_length=24)


class CaptureVoice(Model):
    action: Literal["capture_voice"]
    order_id: str
    revision: int
    text: str = Field(min_length=1, max_length=2000)
    capture_mode: Literal["mock_voice", "live_voice"] = "mock_voice"
    stt_confidence: float | None = Field(default=None, ge=0, le=1)


class ResolveFlag(Model):
    action: Literal["resolve_flag"]
    order_id: str
    revision: int
    flag_id: str
    resolution: Literal[
        "keep_selected_table",
        "use_spoken_table",
        "reviewed_remove_unknown",
        "asked_none_reported",
        "reviewed_keep_note",
    ]


class ConfirmSend(Model):
    action: Literal["confirm_send"]
    order_id: str
    revision: int
    human_confirmed: bool


class OrderAction(Model):
    action: Literal["acknowledge", "retry_zones", "deliver_order"]
    order_id: str


class DishAction(Model):
    action: Literal["start_dish", "ready_dish", "pickup_dish"]
    dish_id: str
    fallback_reason: str | None = Field(default=None, max_length=300)


class CameraStatus(Model):
    action: Literal["camera_status"]
    camera_id: str
    status: Literal["ok", "blocked", "offline"]
    reason: str = Field(min_length=1, max_length=300)


class ZoneObservation(Model):
    action: Literal["zone_observation"]
    zone_id: str
    assignment_version: int
    occupied: bool
    stable_ms: int = Field(ge=0, le=60000)
    hand_present: bool = False


class ReconcileZone(Model):
    action: Literal["reconcile_zone"]
    zone_id: str
    assignment_version: int
    occupied: bool
    reason: str = Field(min_length=1, max_length=500)


class KitchenVoice(Model):
    action: Literal["kitchen_voice"]
    text: str = Field(min_length=1, max_length=1000)
    stt_confidence: float | None = Field(default=None, ge=0, le=1)


class StockObservation(Model):
    action: Literal["stock_observation"]
    zone_id: str
    delta: int | None = None
    stable_ms: int = Field(ge=0)
    hand_present: bool = False


class AcceptStock(Model):
    action: Literal["accept_stock"]
    zone_id: str
    kind: Literal["consume", "return", "restock", "waste", "correction"]
    quantity: int
    observation_id: str | None = None
    order_id: str | None = None
    reason: str = Field(min_length=1, max_length=500)


Payload = Annotated[
    StartOrder
    | EditDraft
    | CaptureVoice
    | ResolveFlag
    | ConfirmSend
    | OrderAction
    | DishAction
    | CameraStatus
    | ZoneObservation
    | ReconcileZone
    | KitchenVoice
    | StockObservation
    | AcceptStock,
    Field(discriminator="action"),
]


class Command(Model):
    schema_version: Literal[2] = 2
    event_id: str = Field(min_length=1, max_length=120)
    source: Literal["tap", "voice", "camera", "system"] = "tap"
    time: AwareDatetime = Field(default_factory=now)
    device_id: str | None = None
    run_id: str | None = "interactive-demo"
    simulated: bool = True
    payload: Payload

    @field_validator("time")
    @classmethod
    def utc_time(cls, value):
        return value.astimezone(UTC)


class Computed(Model):
    order_progress: dict[str, dict[str, int]]
    balances: dict[str, int]
    expected_consumption: dict[str, float]
    analytics_health: dict


class Snapshot(State):
    computed: Computed


class CommandResponse(Model):
    result: dict
    state: Snapshot
    replayed: bool


class SessionRequest(Model):
    actor_id: str


class MatchRequest(Model):
    text: str = Field(min_length=1, max_length=1000)
