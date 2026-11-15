"""Per-bay state machine (CV_SPEC.md 7.3): debounce, hand suppression, arrival/removal."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BayChange:
    kind: str  # "arrived" | "removed"
    before: int
    after: int
    confidence: float


@dataclass
class BayUpdate:
    change: BayChange | None = None
    occluded_timeout: bool = False   # suppression exceeded occlusion_timeout_s (fires once)
    occlusion_cleared: bool = False


@dataclass
class BayTracker:
    debounce_s: float = 0.8
    occlusion_timeout_s: float = 6.0
    stable_count: int = 0
    candidate: int | None = None
    candidate_since: float = 0.0
    candidate_confs: list[float] = field(default_factory=list)
    suppressed_since: float | None = None
    occluded_reported: bool = False
    state: str = "stable"  # stable | active | occluded (for the overlay)

    def update(self, ts: float, raw_count: int, confidence: float, motion: bool) -> BayUpdate:
        out = BayUpdate()
        if motion:
            # a hand/arm is in the bay: never update counts mid-interaction
            self.suppressed_since = self.suppressed_since or ts
            self.candidate = None
            self.candidate_confs = []
            self.state = "active"
            if not self.occluded_reported and ts - self.suppressed_since > self.occlusion_timeout_s:
                self.occluded_reported = True
                self.state = "occluded"
                out.occluded_timeout = True
            return out
        if self.occluded_reported:
            out.occlusion_cleared = True
        self.suppressed_since = None
        self.occluded_reported = False
        self.state = "stable"

        if raw_count == self.stable_count:
            self.candidate = None
            self.candidate_confs = []
            return out
        if raw_count != self.candidate:
            self.candidate = raw_count
            self.candidate_since = ts
            self.candidate_confs = [confidence]
            return out
        self.candidate_confs.append(confidence)
        if ts - self.candidate_since < self.debounce_s:
            return out
        before, after = self.stable_count, raw_count
        conf = sum(self.candidate_confs) / len(self.candidate_confs)
        self.stable_count = after
        self.candidate = None
        self.candidate_confs = []
        out.change = BayChange("arrived" if after > before else "removed", before, after, conf)
        return out
