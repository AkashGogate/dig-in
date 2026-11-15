"""Slot-based occupancy counting for ingredient zones (CV_SPEC.md 6.2).

Each zone polygon (4 corners, clockwise from top-left) is warped to a rectangle
and split into a rows x cols grid. A slot is occupied when the fraction of
pixels differing from the empty reference exceeds occupied_min_fraction.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from cvsvc.config import ZoneConfig
from cvsvc.vision import normalized_diff, polygon_mask

SLOT_PX = 64       # warped size of one slot
SLOT_MARGIN = 0.15  # ignore slot borders (dividers, neighbours' overhang)


@dataclass
class ZoneCount:
    count: int
    occupied: list[bool]      # row-major, len = rows*cols
    fractions: list[float]


class ZoneCounter:
    def __init__(self, cfg: ZoneConfig, reference: np.ndarray) -> None:
        self.cfg = cfg
        self.rows, self.cols = cfg.slots.rows, cfg.slots.cols
        self.size = (self.cols * SLOT_PX, self.rows * SLOT_PX)
        self.mask = polygon_mask(reference.shape, cfg.polygon)
        self._M = self._warp_matrix(cfg.polygon, reference.shape)
        self.reference = self.warp(reference)

    def _warp_matrix(self, polygon, shape) -> np.ndarray:
        if len(polygon) == 4:
            src = np.array(polygon, dtype=np.float32)
        else:  # fall back to the bounding box
            x, y, w, h = cv2.boundingRect(np.array(polygon or [(0, 0), (shape[1], shape[0])], dtype=np.int32))
            src = np.array([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], dtype=np.float32)
        w, h = self.size
        dst = np.array([(0, 0), (w, 0), (w, h), (0, h)], dtype=np.float32)
        return cv2.getPerspectiveTransform(src, dst)

    def warp(self, frame: np.ndarray) -> np.ndarray:
        return cv2.warpPerspective(frame, self._M, self.size)

    def set_reference(self, reference: np.ndarray) -> None:
        self.reference = self.warp(reference)

    def slot_rects(self) -> list[tuple[int, int, int, int]]:
        m = int(SLOT_PX * SLOT_MARGIN)
        return [(c * SLOT_PX + m, r * SLOT_PX + m, SLOT_PX - 2 * m, SLOT_PX - 2 * m)
                for r in range(self.rows) for c in range(self.cols)]

    def count(self, frame: np.ndarray) -> ZoneCount:
        warped = self.warp(frame)
        full = np.full(warped.shape[:2], 255, np.uint8)
        diff = normalized_diff(warped, self.reference, full)
        changed = diff > self.cfg.diff_threshold
        occ, fr = [], []
        for x, y, w, h in self.slot_rects():
            f = float(changed[y:y + h, x:x + w].mean())
            fr.append(round(f, 3))
            occ.append(f >= self.cfg.occupied_min_fraction)
        return ZoneCount(sum(occ), occ, fr)

    def slot_polygons(self) -> list[np.ndarray]:
        """Slot rectangles projected back to frame coordinates (for the overlay)."""
        inv = np.linalg.inv(self._M)
        out = []
        for x, y, w, h in self.slot_rects():
            pts = np.array([[(x, y), (x + w, y), (x + w, y + h), (x, y + h)]], dtype=np.float32)
            out.append(cv2.perspectiveTransform(pts, inv)[0].astype(np.int32))
        return out
