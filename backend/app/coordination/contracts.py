"""Version 1 contract source of truth; /api/v1/contracts exports JSON Schema.

Adapters emit observations. Only validated staff commands mutate operational state.
No frontend/adapter may maintain a competing authoritative order or stock ledger.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


def now() -> str:
    return datetime.now(UTC).isoformat()


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Actor(Model):
    id: str
    name: str
    role: Literal["server", "cook", "lead"]
    section: str


class Table(Model):
    id: str
    section: str
    seats: list[int]


class MenuItem(Model):
    id: str
    name: str
    price_cents: int
    modifiers: list[str]
    recipe: dict[str, int]


class Line(Model):
    id: str = Field(min_length=1, max_length=80)
    seat: int = Field(ge=1)
    menu_id: str
    quantity: int = Field(ge=1, le=12)
    modifiers: list[str] = Field(default_factory=list)
    requests: str = Field(default="", max_length=500)
    course: str = Field(default="main", min_length=1, max_length=80)


class Proposal(Model):
    id: str
    revision: int
    line_id: str | None = None
    quantity: int | None = None
    transcript: str
    question: str | None = None


DishStage = Literal[
    "queued", "preparing", "partially_plated", "plated", "ready", "picked_up", "served"
]


class Dish(Model):
    id: str
    order_id: str
    line_id: str
    seat: int
    menu_id: str
    course: str
    modifiers: list[str]
    requests: str
    stage: DishStage = "queued"
    bay_id: str | None = None


class Amendment(Model):
    line_id: str
    quantity: int = Field(ge=1, le=12)
    revision: int
    acknowledged: bool = False


class Order(Model):
    id: str
    owner: str
    table_id: str | None = None
    revision: int = 1
    status: Literal["draft", "submitting", "submitted"] = "draft"
    status_history: list[str] = Field(default_factory=lambda: ["draft"])
    acknowledged: bool = False
    lines: list[Line] = Field(default_factory=list)
    proposal: Proposal | None = None
    amendments: list[Amendment] = Field(default_factory=list)
    created_at: str = Field(default_factory=now)


class Bay(Model):
    id: str
    capacity: int = 2
    assignment_version: int = 0
    order_id: str | None = None
    course: str | None = None
    dish_ids: list[str] = Field(default_factory=list)
    occupied: bool = False
    unresolved_pickup: bool = False
    convention: Literal["staging", "complete_batches_only"] = "staging"


class Zone(Model):
    id: str
    ingredient: str
    initial: int
    unit: str = "portion"


class Movement(Model):
    id: str
    zone_id: str
    kind: Literal["consume", "return", "restock", "waste", "correction"]
    delta: int
    observation_id: str | None = None
    order_id: str | None = None
    actor_id: str
    reason: str


class Observation(Model):
    id: str
    kind: Literal[
        "ingredient_change",
        "plate_arrival",
        "plate_removal",
        "plate_return",
        "obstruction",
    ]
    target_id: str
    assignment_version: int | None = None
    quantity: int | None = None
    order_id: str | None = None
    disposition: str = "unresolved"
    source: str
    device_id: str | None = None
    occurred_at: str


class Task(Model):
    id: str
    table_id: str
    section: str
    type: Literal["food_run", "guest_request", "help"]
    created_at: str = Field(default_factory=now)
    dish_ids: list[str] = Field(default_factory=list)
    status: Literal["available", "claimed", "blocked", "completed", "cancelled"] = (
        "available"
    )
    owner: str | None = None
    helper_slots: list[str | None] = Field(default_factory=list)
    blocker: str | None = None
    priority_reason: str = "Waiting request; aging prevents starvation"
    urgency: bool = False
    vip: bool = False


class State(Model):
    schema_version: Literal[1] = 1
    actors: dict[str, Actor]
    tables: dict[str, Table]
    menu: dict[str, MenuItem]
    orders: dict[str, Order] = Field(default_factory=dict)
    dishes: dict[str, Dish] = Field(default_factory=dict)
    bays: dict[str, Bay]
    zones: dict[str, Zone]
    movements: list[Movement] = Field(default_factory=list)
    observations: dict[str, Observation] = Field(default_factory=dict)
    tasks: dict[str, Task] = Field(default_factory=dict)
    events: list[dict] = Field(default_factory=list)
    adapter_status: dict[str, str]
    auto_ready_enabled: bool = False
    active_prep: dict[str, str] = Field(default_factory=dict)


class Start(Model):
    action: Literal["start_order"]
    table_id: str | None = None
    use_positioning: bool = False


class Edit(Model):
    action: Literal["edit_draft"]
    order_id: str
    revision: int
    table_id: str
    lines: list[Line] = Field(min_length=1, max_length=24)


class Readback(Model):
    action: Literal["readback"]
    order_id: str
    revision: int
    transcript: str = Field(min_length=1, max_length=2000)
    line_id: str | None = None


class Accept(Model):
    action: Literal["accept_correction"]
    order_id: str
    revision: int
    proposal_id: str


class Send(Model):
    action: Literal["confirm_send"]
    order_id: str
    revision: int
    human_confirmed: bool


class Acknowledge(Model):
    action: Literal["acknowledge"]
    order_id: str


class Amend(Model):
    action: Literal["amend"]
    order_id: str
    revision: int
    line_id: str
    quantity: int = Field(ge=1, le=12)


class AckAmendment(Model):
    action: Literal["ack_amendment"]
    order_id: str
    revision: int


class Advance(Model):
    action: Literal["advance_dish"]
    dish_id: str
    stage: DishStage
    reason: str = Field(default="", max_length=500)


class Assign(Model):
    action: Literal["assign_bay"]
    bay_id: str
    assignment_version: int
    dish_ids: list[str] = Field(min_length=1)


class ReleaseBay(Model):
    action: Literal["release_bay"]
    bay_id: str
    assignment_version: int
    reason: str = Field(min_length=1, max_length=500)


class ReconcileBay(Model):
    action: Literal["reconcile_bay"]
    bay_id: str
    assignment_version: int
    occupied: bool
    reason: str = Field(min_length=1, max_length=500)


class SelectPrep(Model):
    action: Literal["select_prep"]
    order_id: str


class Observe(Model):
    action: Literal["observe"]
    kind: Literal[
        "ingredient_change",
        "plate_arrival",
        "plate_removal",
        "plate_return",
        "obstruction",
    ]
    target_id: str
    assignment_version: int | None = None
    quantity: int | None = Field(default=None, ge=1)
    order_id: str | None = None


class Stock(Model):
    action: Literal["accept_movement"]
    zone_id: str
    kind: Literal["consume", "return", "restock", "waste", "correction"]
    quantity: int
    observation_id: str | None = None
    order_id: str | None = None
    reason: str = Field(min_length=1, max_length=500)


class CreateTask(Model):
    action: Literal["create_task"]
    table_id: str
    type: Literal["guest_request", "help"]
    reason: str = Field(min_length=1, max_length=500)


class TaskAction(Model):
    action: Literal["task_action"]
    task_id: str
    operation: Literal[
        "claim",
        "release",
        "join",
        "leave",
        "helpers",
        "split",
        "block",
        "cancel",
        "complete",
        "urgent",
    ]
    additional_helpers: int = Field(default=0, ge=0, le=6)
    reason: str = Field(default="", max_length=500)


Payload = Annotated[
    Start
    | Edit
    | Readback
    | Accept
    | Send
    | Acknowledge
    | Amend
    | AckAmendment
    | Advance
    | Assign
    | ReleaseBay
    | ReconcileBay
    | SelectPrep
    | Observe
    | Stock
    | CreateTask
    | TaskAction,
    Field(discriminator="action"),
]


class Command(Model):
    id: str = Field(min_length=1, max_length=100)
    schema_version: Literal[1] = 1
    source: Literal["manual", "voice", "mock_camera", "camera", "positioning"] = (
        "manual"
    )
    kind: Literal["command", "observation"] = "command"
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    device_id: str | None = None
    correlation_id: str | None = None
    payload: Payload


class DemoSession(Model):
    actor_id: str


class Computed(Model):
    balances: dict[str, int]
    expected_consumption: dict[str, int]
    ticket_stages: dict[str, str]
    ranked_tasks: list[Task]
    task_blockers: dict[str, list[str]]


class Snapshot(State):
    computed: Computed


class SessionResponse(Model):
    session_id: str
    actor: Actor


class CommandResponse(Model):
    result: dict
    state: Snapshot
    replayed: bool


def schema() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": Command.model_json_schema(),
        "state": Snapshot.model_json_schema(),
    }
