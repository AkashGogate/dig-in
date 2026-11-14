"""Canonical v2 accepted-event contract shared by core and analytics.

Event types are an extensible dotted vocabulary: core validates commands before
emitting facts; an arbitrary incoming fact must never bypass domain validation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

EVENT_TYPES = (
    "order.submitted",
    "order.acknowledged",
    "zones.assigned",
    "zones.waiting",
    "dish.started",
    "dish.ready",
    "order.ready",
    "dish.picked_up",
    "order.picked_up",
    "order.delivered",
    "zone.unexpected",
    "camera.status",
    "stock.changed",
    "draft.created",
    "draft.updated",
    "draft.flag_resolved",
    "zone.reconciled",
    "camera.observation",
    "zones.retry_requested",
    "voice.clarification",
    "stock.observation",
)


class CanonicalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2] = 2
    event_id: str = Field(min_length=1, max_length=200)
    order_id: str | None = None
    dish_id: str | None = None
    type: str = Field(pattern=r"^[a-z][a-z_]*\.[a-z][a-z_]*$")
    source: Literal["tap", "voice", "camera", "system"]
    actor: str = Field(min_length=1, max_length=200)
    time: AwareDatetime
    received_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str | None = None
    simulated: bool = False
    outcome: Literal["accepted", "observed"] = "accepted"
    payload: dict = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def exclude_capture_content(cls, value):
        """Fail closed against accidentally exporting raw capture content."""
        forbidden = {
            "transcript",
            "raw_transcript",
            "raw_text",
            "audio",
            "raw_audio",
            "audio_bytes",
            "recording",
            "video",
            "raw_video",
        }

        def inspect(item):
            if isinstance(item, dict):
                for key, nested in item.items():
                    if str(key).lower() in forbidden:
                        raise ValueError(
                            "Raw audio/transcript/video is excluded from analytics"
                        )
                    inspect(nested)
            elif isinstance(item, (list, tuple)):
                for nested in item:
                    inspect(nested)

        inspect(value)
        return value

    def export(self) -> dict:
        return self.model_dump(mode="json")
