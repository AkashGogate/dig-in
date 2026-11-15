"""Shape-based plate detection: plates are large circles seen from above.

Independent of plate pattern/colour, counter colour/texture and the camera's auto white
balance: it uses edge geometry only (OpenCV HOUGH_GRADIENT_ALT, which scores how circular
each candidate is). A plate's rim rings give concentric circles; those are merged and the
outermost kept. Each plate is assigned to the bay containing its centre, so a plate that
hangs over a bay edge still belongs to exactly one bay.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Plate:
    x: int
    y: int
    r: int

    def contour(self) -> np.ndarray:
        pts = cv2.ellipse2Poly((self.x, self.y), (self.r, self.r), 0, 0, 360, 10)
        return pts.reshape(-1, 1, 2)


class PlateFinder:
    def __init__(self, min_radius_px: int = 90, max_radius_px: int = 260, quality: float = 0.75,
                 scale: float = 0.5, canny_high: int = 120) -> None:
        self.min_r = min_radius_px
        self.max_r = max_radius_px
        self.quality = quality      # 0..1, HOUGH_GRADIENT_ALT circularity threshold
        self.scale = scale
        self.canny_high = canny_high

    def find(self, frame: np.ndarray) -> list[Plate]:
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(g, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_AREA)
        small = cv2.GaussianBlur(small, (5, 5), 1.5)
        s = self.scale
        found = cv2.HoughCircles(small, cv2.HOUGH_GRADIENT_ALT, dp=1.5, minDist=max(1.0, self.min_r * s * 0.5),
                                 param1=self.canny_high, param2=self.quality,
                                 minRadius=int(self.min_r * s), maxRadius=int(self.max_r * s))
        if found is None:
            return []
        cands = sorted((Plate(int(x / s), int(y / s), int(r / s)) for x, y, r in found[0]),
                       key=lambda p: -p.r)
        plates: list[Plate] = []
        for c in cands:  # largest first; drop concentric rim rings and circles inside a kept plate
            if any((c.x - p.x) ** 2 + (c.y - p.y) ** 2 < (0.5 * p.r) ** 2 for p in plates):
                continue
            plates.append(c)
        return plates


def assign_to_bays(plates: list[Plate], bays: dict[str, np.ndarray]) -> dict[str, list[Plate]]:
    out: dict[str, list[Plate]] = {b: [] for b in bays}
    for p in plates:
        for bid, poly in bays.items():
            if cv2.pointPolygonTest(poly, (float(p.x), float(p.y)), False) >= 0:
                out[bid].append(p)
                break
    return out
