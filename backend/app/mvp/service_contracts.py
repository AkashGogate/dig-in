"""Additive v2 service handoff contract; never a second cooking state machine.

Explicit staff-authored notes may be stored for the recipient. Capture adapters
must not place transcripts/audio in these records. Analytics receives correlation
metadata only, not authored note text or generated device summaries.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

Audience = Literal["server", "kitchen"]
UpdateKind = Literal["delay", "needs_attention", "pickup_request", "availability"]


class ServiceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServiceUpdate(ServiceModel):
    id: str
    revision: int = 1
    order_id: str
    kind: UpdateKind
    note: str = ""
    sender_id: str
    recipient_id: str
    status: Literal["unread", "acknowledged", "resolved"] = "unread"
    created_at: AwareDatetime
    received_at: AwareDatetime
    acknowledged_at: AwareDatetime | None = None
    resolved_at: AwareDatetime | None = None


class PublishServiceUpdate(ServiceModel):
    action: Literal["publish_service_update"]
    order_id: str
    kind: UpdateKind
    note: str = Field(default="", max_length=300)

    @field_validator("note")
    @classmethod
    def authored_note(cls, value):
        # Keep explicit typed notes compact; no raw capture command is accepted.
        return " ".join(value.split())


class RespondServiceUpdate(ServiceModel):
    action: Literal["acknowledge_service_update", "resolve_service_update"]
    update_id: str
    revision: int = Field(ge=1)


class ServiceCounts(ServiceModel):
    orders: int
    awaiting_acknowledgment: int
    waiting_for_zones: int
    cooking_units: int
    ready_for_pickup: int
    unread_updates: int
    open_updates: int


class ServiceOrder(ServiceModel):
    order_id: str
    table_id: str
    status: str
    zone_status: str
    ready: int
    total: int
    picked_up: int
    ready_for_pickup: int
    next_action: str | None


class ServiceDish(ServiceModel):
    dish_id: str
    order_id: str
    table_id: str
    item_name: str
    modifier_names: list[str]
    modifiers: list[str]
    seat: int | None
    requests: str
    zone_needs_review: bool
    stage: str
    station: str | None
    zone_id: str | None
    started_at: AwareDatetime | None
    typical_minutes: float | None
    elapsed_seconds: int | None
    next_action: str | None


class ServiceUpdateView(ServiceUpdate):
    currently_actionable: bool
    actionability_reason: str
    current_ready_for_pickup: int


class ServiceSummary(ServiceModel):
    schema_version: Literal[2] = 2
    audience: Audience
    actor_id: str
    generated_at: AwareDatetime
    counts: ServiceCounts
    orders: list[ServiceOrder]
    lineup: list[ServiceDish]
    updates: list[ServiceUpdateView]
    text: str
