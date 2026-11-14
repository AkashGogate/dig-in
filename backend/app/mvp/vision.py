"""CV workstream seam: sampled stability/hand detection is adapter work.

The mock trusts declared durations; it does not prove stability from images.
Core alone allocates/reuses zones and accepts/rejects the resulting evidence.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol

from app.mvp.contracts import Command, ZoneObservation


class VisionAdapter(Protocol):
    def observations(self) -> AsyncIterator[Command]:
        """Emit camera-status or versioned zone/stock observation commands.

        Keep raw frames transient. Use stable event IDs across retries. Report
        blocked/offline explicitly; never encode an unavailable feed as empty.
        """
        ...


def mock_zone_command(
    *,
    event_id: str,
    zone_id: str,
    assignment_version: int,
    occupied: bool,
    time: datetime,
    stable_ms: int = 1600,
    hand_present: bool = False,
    run_id: str = "vision-simulation",
) -> Command:
    return Command(
        event_id=event_id,
        source="camera",
        time=time,
        device_id="plating-cam",
        run_id=run_id,
        simulated=True,
        payload=ZoneObservation(
            action="zone_observation",
            zone_id=zone_id,
            assignment_version=assignment_version,
            occupied=occupied,
            stable_ms=stable_ms,
            hand_present=hand_present,
        ),
    )
