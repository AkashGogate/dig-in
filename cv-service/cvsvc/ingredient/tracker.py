"""Per-zone state machine (CV_SPEC.md 6.3).

STABLE --motion--> ACTIVE --no motion for settle_s--> SETTLING --stable median--> RESOLVE
ACTIVE --activity > occlusion_timeout_s--> PENDING (occlusion_timeout)
RESOLVE compares against the pre-interaction baseline; the baseline only moves
after an event is emitted or a pending item is resolved (resolve()).
A hand entering a zone never produces an event by itself.
"""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field


@dataclass
class ZoneResult:
    kind: str  # picked | returned | pending
    before: int
    after: int | None
    confidence: float
    reason: str | None = None
    version_at_start: int | None = None  # active-ticket context version when the interaction began


@dataclass
class ZoneTracker:
    baseline: int
    settle_s: float = 1.0
    occlusion_timeout_s: float = 6.0
    large_delta_limit: int = 4
    settle_frames: int = 10
    state: str = "stable"  # stable | active | settling | pending
    active_since: float = 0.0
    last_motion: float = 0.0
    settling_since: float = 0.0
    version_at_start: int | None = None
    baseline_brightness: float | None = None
    window: deque = field(default_factory=lambda: deque(maxlen=10))
    brightness_window: deque = field(default_factory=lambda: deque(maxlen=10))

    def __post_init__(self) -> None:
        self.window = deque(maxlen=self.settle_frames)
        self.brightness_window = deque(maxlen=self.settle_frames)

    def resolve(self, count: int, brightness: float | None = None) -> None:
        """Staff correction / post-event baseline set."""
        self.baseline = count
        self.state = "stable"
        self.window.clear()
        if brightness is not None:
            self.baseline_brightness = brightness

    def update(self, ts: float, raw_count: int, motion: bool, brightness: float,
               context_version: int | None = None) -> ZoneResult | None:
        if self.baseline_brightness is None:
            self.baseline_brightness = brightness

        if self.state == "pending":
            return None  # frozen until staff resolve (POST /zones/{id}/resolve)

        if self.state == "stable":
            if motion:
                self.state = "active"
                self.active_since = self.last_motion = ts
                self.version_at_start = context_version
            return None

        if motion:
            self.last_motion = ts
            if self.state == "settling":
                self.state = "active"
                self.window.clear()
            if ts - self.active_since > self.occlusion_timeout_s:
                self.state = "pending"
                return ZoneResult("pending", self.baseline, raw_count, 0.3, "occlusion_timeout",
                                  self.version_at_start)
            return None

        if self.state == "active":
            if ts - self.last_motion < self.settle_s:
                if ts - self.active_since > self.occlusion_timeout_s:
                    self.state = "pending"
                    return ZoneResult("pending", self.baseline, raw_count, 0.3, "occlusion_timeout",
                                      self.version_at_start)
                return None
            self.state = "settling"
            self.settling_since = ts
            self.window.clear()
            self.brightness_window.clear()

        # settling
        self.window.append(raw_count)
        self.brightness_window.append(brightness)
        if len(self.window) < self.window.maxlen:  # type: ignore[operator]
            return None
        spread = max(self.window) - min(self.window)
        median = int(statistics.median(self.window))
        agree = sum(1 for c in self.window if c == median) / len(self.window)
        if spread > 0:
            if ts - self.settling_since > 3 * self.settle_s:
                self.state = "pending"
                return ZoneResult("pending", self.baseline, median, round(agree * 0.5, 3), "unstable_count",
                                  self.version_at_start)
            return None
        return self._resolve_interaction(median, agree)

    def _resolve_interaction(self, new_count: int, agree: float) -> ZoneResult | None:
        before = self.baseline
        delta = new_count - before
        conf = agree
        b = statistics.mean(self.brightness_window) if self.brightness_window else None
        if b is not None and self.baseline_brightness and abs(b - self.baseline_brightness) / self.baseline_brightness > 0.15:
            conf *= 0.7
        self.window.clear()
        if delta == 0:
            self.state = "stable"
            return None
        if abs(delta) > self.large_delta_limit:
            self.state = "pending"
            return ZoneResult("pending", before, new_count, round(conf * 0.5, 3), "large_delta",
                              self.version_at_start)
        self.baseline = new_count
        self.state = "stable"
        if b is not None:
            self.baseline_brightness = b
        return ZoneResult("picked" if delta < 0 else "returned", before, new_count, round(conf, 3), None,
                          self.version_at_start)
