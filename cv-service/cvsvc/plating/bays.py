"""Per-bay plate counting (CV_SPEC.md 7.2)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from cvsvc.config import BayConfig
from cvsvc.vision import normalized_diff, polygon_mask

_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))


@dataclass
class PlateCount:
    count: int
    confidence: float
    contours: list[np.ndarray]  # full-frame coordinates (for the overlay)


class BayCounter:
    def __init__(self, cfg: BayConfig, reference: np.ndarray, max_plates: int = 4) -> None:
        self.cfg = cfg
        self.reference = reference
        self.max_plates = max_plates
        full_mask = polygon_mask(reference.shape, cfg.polygon)
        # work on the polygon's bounding box only (keeps 3 bays well above 10 FPS)
        x, y, w, h = cv2.boundingRect(full_mask) if full_mask.any() else (0, 0, *reference.shape[1::-1])
        self.roi = (x, y, w, h)
        self.mask = full_mask[y:y + h, x:x + w]
        self.reference = reference[y:y + h, x:x + w]

    def set_reference(self, reference: np.ndarray) -> None:
        x, y, w, h = self.roi
        self.reference = reference[y:y + h, x:x + w]

    def crop(self, frame: np.ndarray) -> np.ndarray:
        x, y, w, h = self.roi
        return frame[y:y + h, x:x + w]

    def foreground(self, frame: np.ndarray) -> np.ndarray:
        """`frame` is the full camera frame; returns the foreground mask in ROI coordinates."""
        diff = normalized_diff(self.crop(frame), self.reference, self.mask)
        _, fg = cv2.threshold(diff, self.cfg.diff_threshold, 255, cv2.THRESH_BINARY)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, _KERNEL)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, _KERNEL, iterations=2)
        return fg

    def count(self, frame: np.ndarray) -> PlateCount:
        fg = self.foreground(frame)
        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
                                       offset=self.roi[:2])
        n, conf_penalty, kept = 0, 0.0, []
        lo, hi = self.cfg.min_plate_area_px, self.cfg.max_plate_area_px
        for c in contours:
            area = cv2.contourArea(c)
            if area < lo:
                continue
            perim = cv2.arcLength(c, True)
            circ = 4 * math.pi * area / (perim * perim) if perim > 0 else 0.0
            if lo <= area <= hi and circ >= self.cfg.min_circularity:
                n += 1
                kept.append(c)
                continue
            # merged blob (two touching plates) or odd shape: try a distance-transform split
            split = self._split(fg, c)
            if split >= 2:
                n += split
                conf_penalty += 0.1
            elif area <= hi * 1.2:
                n += 1  # one plate, unusual shape
                conf_penalty += 0.2
            else:
                n += max(1, round(area / ((lo + hi) / 2)))
                conf_penalty += 0.35
            kept.append(c)
        n = min(n, self.max_plates)
        return PlateCount(n, max(0.1, 1.0 - conf_penalty), kept)

    def _split(self, fg: np.ndarray, contour: np.ndarray) -> int:
        blob = np.zeros_like(fg)
        x, y = self.roi[:2]
        cv2.drawContours(blob, [contour - np.array([x, y])], -1, 255, -1)
        dist = cv2.distanceTransform(blob, cv2.DIST_L2, 5)
        if dist.max() <= 0:
            return 0
        _, peaks = cv2.threshold(dist, 0.6 * dist.max(), 255, cv2.THRESH_BINARY)
        n, _, stats, _ = cv2.connectedComponentsWithStats(peaks.astype(np.uint8))
        # ignore tiny peak fragments
        min_core = 0.02 * self.cfg.min_plate_area_px
        return sum(1 for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_core)
