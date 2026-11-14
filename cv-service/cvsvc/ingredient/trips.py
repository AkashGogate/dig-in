"""Trip detection (ingredient `mode: trips`).

A trip = motion appears inside a zone polygon and then stops for trip_settle_s.
CV does not count portions; the backend subtracts the recipe quantity per trip.

Ambiguity is never a silent decision:
  - motion in another zone during most of the trip (e.g. someone walking past a
    straight-on camera) -> pending_review, reason "multi_zone"
  - motion lasting longer than occlusion_timeout_s -> pending_review, reason "long_occlusion"
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
    state: str = "stable"  # stable | active | pending (for the overlay)
    started: float = 0.0
    last_motion: float = 0.0
    frames: int = 0
    overlap_frames: int = 0
    version_at_start: int | None = None
    trips: int = 0
    long_reported: bool = False

    def update(self, ts: float, motion: bool, other_zone_motion: bool,
               context_version: int | None = None) -> TripResult | None:
        if self.state == "stable":
            if motion:
                self.state = "active"
                self.started = self.last_motion = ts
                self.frames, self.overlap_frames = 1, int(other_zone_motion)
                self.version_at_start = context_version
                self.long_reported = False
            return None

        # active or pending (long occlusion already reported; wait for it to clear)
        if motion:
            self.last_motion = ts
            self.frames += 1
            self.overlap_frames += int(other_zone_motion)
            if not self.long_reported and ts - self.started > self.max_trip_s:
                self.long_reported = True
                self.state = "pending"
                return TripResult(ts - self.started, 0.3, "long_occlusion", self.version_at_start)
            return None
        if ts - self.last_motion < self.settle_s:
            return None
        duration = self.last_motion - self.started
        was_long = self.long_reported
        self.state = "stable"
        if was_long:
            return None  # already surfaced for review
        if duration < self.min_trip_s:
            return None  # flicker
        overlap = self.overlap_frames / max(self.frames, 1)
        self.trips += 1
        if overlap > 0.5:
            return TripResult(duration, round(1 - overlap, 3), "multi_zone", self.version_at_start)
        return TripResult(duration, round(max(0.5, 1 - overlap), 3), None, self.version_at_start)
