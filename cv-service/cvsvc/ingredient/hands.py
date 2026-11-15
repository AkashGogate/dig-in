"""Hand-based trip detection (ingredient `mode: trips`, `trip_detector: hands`).

A trip is a *hand* inside a zone, not just motion: with a straight-on camera the person
reaching is always between the camera and the shelf, so bodies, heads and passers-by
cover zones constantly. A trip counts only when a detected hand (index fingertip, else
palm centre) stays inside a zone for at least `dwell_s`, once per entry. A hand crossing
other zones on its way (typically <= 0.2 s each) does not count.

Uses MediaPipe's hand landmarker (CPU, ~6 ms per 640x360 frame). The model file is not
committed; fetch it with:
  curl -L -o models/hand_landmarker.task \\
    https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

INDEX_TIP = 8
PALM = (0, 5, 9, 13, 17)


@dataclass
class Hand:
    tip: tuple[float, float]
    palm: tuple[float, float]
    size: float            # mean of landmark bbox width/height, full-frame px
    points: np.ndarray     # 21 x 2, full-frame px (for the overlay)


class HandDetector:
    def __init__(self, model_path: str, max_hands: int = 2, detect_width: int = 640,
                 min_confidence: float = 0.4) -> None:
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"hand model not found at {model_path}. Download it with:\n  curl -L -o {model_path} "
                "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/"
                "hand_landmarker.task")
        import mediapipe as mp  # imported lazily so the rest of the service works without it
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        opts = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO, num_hands=max_hands,
            min_hand_detection_confidence=min_confidence, min_hand_presence_confidence=min_confidence,
            min_tracking_confidence=min_confidence)
        self._lm = vision.HandLandmarker.create_from_options(opts)
        self.detect_width = detect_width
        self._last_ms = -1

    def detect(self, frame: np.ndarray, ts: float) -> list[Hand]:
        h, w = frame.shape[:2]
        scale = self.detect_width / w
        small = cv2.resize(frame, (self.detect_width, int(h * scale)), interpolation=cv2.INTER_AREA)
        ms = max(int(ts * 1000), self._last_ms + 1)  # VIDEO mode needs strictly increasing timestamps
        self._last_ms = ms
        img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        res = self._lm.detect_for_video(img, ms)
        hands = []
        for hl in res.hand_landmarks:
            pts = np.array([(p.x * w, p.y * h) for p in hl], dtype=np.float32)
            palm = pts[list(PALM)].mean(axis=0)
            size = float(np.ptp(pts[:, 0]) + np.ptp(pts[:, 1])) / 2
            hands.append(Hand((float(pts[INDEX_TIP][0]), float(pts[INDEX_TIP][1])),
                              (float(palm[0]), float(palm[1])), size, pts))
        return hands


def zone_of(hand: Hand, zones: dict[str, np.ndarray]) -> str | None:
    """Zone containing the fingertip, else the palm centre."""
    for pt in (hand.tip, hand.palm):
        for zid, poly in zones.items():
            if cv2.pointPolygonTest(poly, pt, False) >= 0:
                return zid
    return None


@dataclass
class HandTripResult:
    duration_s: float
    confidence: float
    version_at_start: int | None


@dataclass
class HandTripTracker:
    """One trip per hand entry that dwells >= dwell_s. Brief detection dropouts (<= gap_s)
    don't end an entry."""
    dwell_s: float = 0.35
    gap_s: float = 0.25
    state: str = "stable"  # stable | active (hand inside) — for the overlay
    inside: bool = False
    counted: bool = False
    entered: float = 0.0
    last_in: float = 0.0
    frames_in: int = 0
    version_at_start: int | None = None
    trips: int = 0

    def update(self, ts: float, hand_in: bool, context_version: int | None = None) -> HandTripResult | None:
        if hand_in:
            if not self.inside:
                self.inside, self.counted = True, False
                self.entered, self.frames_in = ts, 0
                self.version_at_start = context_version
            self.last_in = ts
            self.frames_in += 1
            self.state = "active"
            if not self.counted and ts - self.entered >= self.dwell_s:
                self.counted = True
                self.trips += 1
                span = max(ts - self.entered, 1e-6)
                # confidence: how continuously the hand was seen during the dwell (15 fps nominal)
                conf = min(1.0, self.frames_in / (span * 15 + 1))
                return HandTripResult(round(span, 2), round(max(conf, 0.5), 3), self.version_at_start)
            return None
        if self.inside and ts - self.last_in > self.gap_s:
            self.inside = False
            self.state = "stable"
        return None
