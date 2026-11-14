"""Camera health classification (CV_SPEC.md section 9).

lost       no frame for > lost_after_s
obstructed mean luminance < dark_threshold, OR Laplacian variance < min(blur_threshold, 25% of the reference's),
           OR > big_change_fraction of pixels changed vs the rolling background for
           > big_change_hold_s while no zone is ACTIVE (a hand in one zone must not trigger it)
degraded   lighting shifted > 25% from calibration, or focus down > 40%
ok         otherwise
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from cvsvc.config import HealthConfig

_SMALL = (160, 90)


def frame_stats(frame: np.ndarray) -> tuple[float, float, np.ndarray]:
    gray = cv2.cvtColor(cv2.resize(frame, _SMALL, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    lum = float(gray.mean())
    focus = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return lum, focus, gray


@dataclass
class HealthTransition:
    state: str
    reason: str | None
    since: float


class HealthMonitor:
    def __init__(self, cfg: HealthConfig, reference: np.ndarray | None = None) -> None:
        self.cfg = cfg
        self.state = "ok"
        self.reason: str | None = None
        self.since = 0.0
        self.last_frame_ts: float | None = None
        self.bg: np.ndarray | None = None
        self.first_frame_ts: float | None = None
        self.big_change_since: float | None = None
        self.ref_lum: float | None = None
        self.ref_focus: float | None = None
        self.last_lum = 0.0
        self.last_focus = 0.0
        if reference is not None:
            self.set_reference(reference)

    def set_reference(self, reference: np.ndarray) -> None:
        self.ref_lum, self.ref_focus, _ = frame_stats(reference)

    def _set(self, ts: float, state: str, reason: str | None) -> HealthTransition | None:
        if state == self.state and reason == self.reason:
            return None
        changed_state = state != self.state
        self.state, self.reason = state, reason
        if changed_state:
            self.since = ts
            return HealthTransition(state, reason, ts)
        return None  # same state, new reason: not a transition

    def tick(self, ts: float) -> HealthTransition | None:
        """Call regularly even without frames to detect `lost`."""
        if self.last_frame_ts is None:
            if self.since == 0.0:
                self.since = ts
            if ts - self.since > self.cfg.lost_after_s and self.state != "lost":
                return self._set(ts, "lost", "no_frames")
            return None
        if ts - self.last_frame_ts > self.cfg.lost_after_s:
            return self._set(ts, "lost", "no_frames")
        return None

    def update(self, ts: float, frame: np.ndarray, any_zone_active: bool = False) -> HealthTransition | None:
        self.last_frame_ts = ts
        lum, focus, gray = frame_stats(frame)
        self.last_lum, self.last_focus = lum, focus
        g = gray.astype(np.float32)
        big = False
        if self.first_frame_ts is None:
            self.first_frame_ts = ts
        if self.bg is None or ts - self.first_frame_ts < self.cfg.warmup_s:
            self.bg = g.copy()  # camera auto-exposure settles during warm-up; don't judge yet
        else:
            # match overall brightness first so an auto-exposure shift is not a "blocked view"
            g_n = g * (float(self.bg.mean()) / max(float(g.mean()), 1.0))
            frac = float((cv2.absdiff(g_n, self.bg) > 30).mean())
            big = frac > self.cfg.big_change_fraction
            if not big:
                cv2.accumulateWeighted(g, self.bg, 0.05)  # don't learn the obstruction into the background
        if big and not any_zone_active:
            self.big_change_since = self.big_change_since or ts
        else:
            self.big_change_since = None

        if ts - (self.first_frame_ts or ts) < self.cfg.warmup_s:
            return None  # camera still settling (first frames are often black)
        if lum < self.cfg.dark_threshold:
            return self._set(ts, "obstructed", "dark")
        # blur only counts relative to the calibrated scene: a plain, low-texture counter
        # must not read as "obstructed"
        blur_limit = self.cfg.blur_threshold if self.ref_focus is None else min(self.cfg.blur_threshold,
                                                                                0.25 * self.ref_focus)
        if focus < blur_limit:
            return self._set(ts, "obstructed", "blur")
        if self.big_change_since is not None and ts - self.big_change_since > self.cfg.big_change_hold_s:
            return self._set(ts, "obstructed", "view_blocked")
        if self.state == "obstructed" and self.reason == "view_blocked" and big:
            return None  # still blocked
        if self.ref_lum and abs(lum - self.ref_lum) / self.ref_lum > self.cfg.degraded_light_shift:
            return self._set(ts, "degraded", "lighting_shift")
        if self.ref_focus and focus < (1 - self.cfg.degraded_focus_drop) * self.ref_focus:
            return self._set(ts, "degraded", "focus_drop")
        return self._set(ts, "ok", None)

    @property
    def frozen(self) -> bool:
        return self.state in ("obstructed", "lost")
