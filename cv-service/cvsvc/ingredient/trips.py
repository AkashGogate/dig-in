"""Trip detection (ingredient `mode: trips`).

A trip = motion appears inside a zone polygon and then stops for trip_settle_s.
CV does not count portions; the backend subtracts the recipe quantity per trip.

With a straight-on camera an arm reaching into one zone crosses others on the way,
so each frame credits only the *dominant* zone (largest fraction of its area moving).
At the end of a burst of motion in a zone:
  - dominant for >= min_dominant_ratio of its active frames  -> trip (observed)
  - dominant for some frames but less than that              -> pending_review "multi_zone"
  - (almost) never dominant: the arm just passed through     -> nothing
  - a body in front of the camera (large share of the whole frame moving, or 3+ zones at once)
    for most of it: someone walking past -> nothing. Walking past is not an interaction.
  - a body for part of it (a reach mixed with someone passing) -> pending_review "multi_zone"
  - motion longer than max_trip_s (and not a body)            -> pending_review "long_occlusion"
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TripResult:
    duration_s: float
    confidence: float
    reason: str | None
    version_at_start: int | None


@dataclass
class TripTracker:
    min_trip_s: float = 0.25
    settle_s: float = 0.6
    max_trip_s: float = 6.0
    min_dominant_ratio: float = 0.5
    pass_through_ratio: float = 0.2
    state: str = "stable"  # stable | active | pending (for the overlay)
    started: float = 0.0
    last_motion: float = 0.0
    frames: int = 0
    dominant_frames: int = 0
    crowded_frames: int = 0
    version_at_start: int | None = None
    trips: int = 0
    long_reported: bool = False

    def update(self, ts: float, motion: bool, dominant: bool = True, crowded: bool = False,
               context_version: int | None = None) -> TripResult | None:
        """`crowded` = a body is in front of the camera this frame (not a hand reaching in)."""
        if self.state == "stable":
            if motion:
                self.state = "active"
                self.started = self.last_motion = ts
                self.frames, self.dominant_frames, self.crowded_frames = 1, int(dominant), int(crowded)
                self.version_at_start = context_version
                self.long_reported = False
            return None

        # active, or pending after a long occlusion was reported (wait for it to clear)
        if motion:
            self.last_motion = ts
            self.frames += 1
            self.dominant_frames += int(dominant)
            self.crowded_frames += int(crowded)
            if not self.long_reported and ts - self.started > self.max_trip_s:
                self.long_reported = True
                if self.crowded_frames / self.frames > 0.5:
                    return None  # someone standing in front, not an interaction
                self.state = "pending"
                return TripResult(ts - self.started, 0.3, "long_occlusion", self.version_at_start)
            return None
        if ts - self.last_motion < self.settle_s:
            return None
        duration = self.last_motion - self.started
        was_long = self.long_reported
        self.state = "stable"
        if was_long or duration < self.min_trip_s:
            return None
        dom = self.dominant_frames / max(self.frames, 1)
        crowd = self.crowded_frames / max(self.frames, 1)
        if crowd > 0.5:
            return None  # walking past / standing in front: not an interaction
        if crowd > 0.2:
            self.trips += 1
            return TripResult(duration, round(1 - crowd, 3), "multi_zone", self.version_at_start)
        if dom < self.pass_through_ratio:
            return None  # the arm passed through on the way to another zone
        self.trips += 1
        if dom < self.min_dominant_ratio:
            return TripResult(duration, round(dom, 3), "multi_zone", self.version_at_start)
        return TripResult(duration, round(dom, 3), None, self.version_at_start)
