"""Shared classical-CV helpers: polygon masks, brightness-normalized diff, motion-in-polygon."""
from __future__ import annotations

import cv2
import numpy as np


def polygon_mask(shape: tuple[int, int], polygon: list[tuple[int, int]]) -> np.ndarray:
    mask = np.zeros(shape[:2], dtype=np.uint8)
    if polygon:
        cv2.fillPoly(mask, [np.array(polygon, dtype=np.int32)], 255)
    return mask


def normalized_diff(frame: np.ndarray, reference: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Per-pixel color difference vs. the empty reference inside `mask`, after matching
    mean luminance so lighting drift does not read as stock / plates. Returns uint8."""
    f_lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)
    r_lab = cv2.cvtColor(reference, cv2.COLOR_BGR2LAB).astype(np.float32)
    m = mask > 0
    if m.any():
        f_mean = f_lab[..., 0][m].mean()
        r_mean = r_lab[..., 0][m].mean()
        if f_mean > 1:
            f_lab[..., 0] *= r_mean / f_mean
    d = np.abs(f_lab - r_lab)
    # luminance counts half: a shadow should matter less than a colour change
    diff = np.maximum(d[..., 0] * 0.5, np.maximum(d[..., 1], d[..., 2]) * 1.5)
    diff = np.clip(diff, 0, 255).astype(np.uint8)
    diff[~m] = 0
    return diff


def mean_luminance(frame: np.ndarray, mask: np.ndarray | None = None) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if mask is not None and (mask > 0).any():
        return float(gray[mask > 0].mean())
    return float(gray.mean())


class MotionDetector:
    """Frame differencing against a short rolling background, restricted to a polygon."""

    def __init__(self, mask: np.ndarray, min_area_px: int, alpha: float = 0.2, threshold: int = 25) -> None:
        """`mask` is full-frame; only its bounding box is processed."""
        if mask.any():
            x, y, w, h = cv2.boundingRect(mask)
        else:
            x, y, (h, w) = 0, 0, mask.shape[:2]
        self.roi = (x, y, w, h)
        self.mask = mask[y:y + h, x:x + w]
        self.min_area_px = min_area_px
        self.alpha = alpha
        self.threshold = threshold
        self.bg: np.ndarray | None = None
        self.last_area = 0

    def update(self, gray: np.ndarray) -> bool:
        """`gray` is the full frame."""
        x, y, w, h = self.roi
        g = cv2.GaussianBlur(gray[y:y + h, x:x + w], (5, 5), 0).astype(np.float32)
        if self.bg is None:
            self.bg = g.copy()
            return False
        d = cv2.absdiff(g, self.bg)
        cv2.accumulateWeighted(g, self.bg, self.alpha)
        moving = (d > self.threshold) & (self.mask > 0)
        self.last_area = int(moving.sum())
        return self.last_area >= self.min_area_px


class PresenceDetector:
    """Share of the frame that differs from a slowly learned picture of the empty scene.

    Unlike frame differencing, a person standing still in front of the camera keeps counting
    at their full size. The background only learns where nothing is present (plus a very slow
    global drift so lighting changes are absorbed)."""

    def __init__(self, size: tuple[int, int] = (160, 90), threshold: int = 30,
                 alpha_free: float = 0.05, alpha_drift: float = 0.002) -> None:
        self.size = size
        self.threshold = threshold
        self.alpha_free = alpha_free
        self.alpha_drift = alpha_drift
        self.bg: np.ndarray | None = None
        self.fraction = 0.0

    def update(self, gray: np.ndarray) -> float:
        g = cv2.GaussianBlur(cv2.resize(gray, self.size, interpolation=cv2.INTER_AREA), (5, 5), 0)
        g = g.astype(np.float32)
        if self.bg is None:
            self.bg = g.copy()
            return 0.0
        # no brightness matching here: a person entering shifts the frame mean and would cancel out
        present = np.abs(g - self.bg) > self.threshold
        self.fraction = float(present.mean())
        free = (~present).astype(np.uint8)
        cv2.accumulateWeighted(g, self.bg, self.alpha_free, mask=free)
        cv2.accumulateWeighted(g, self.bg, self.alpha_drift)
        return self.fraction
