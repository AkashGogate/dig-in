import cv2
import numpy as np
import pytest

from cvsvc.config import BayConfig
from cvsvc.plating.bays import BayCounter
from cvsvc.plating.tracker import BayTracker

W, H = 640, 480
BAY = BayConfig(id="A", polygon=[(20, 20), (620, 20), (620, 460), (20, 460)],
                min_plate_area_px=4000, max_plate_area_px=40000)


def counter_frame(brightness=60):
    img = np.full((H, W, 3), brightness, np.uint8)
    noise = np.random.default_rng(0).integers(0, 6, (H, W, 3), dtype=np.uint8)
    return cv2.add(img, noise)


def with_plates(centers, r=60, base=None):
    img = counter_frame() if base is None else base.copy()
    for c in centers:
        cv2.circle(img, c, r, (235, 235, 235), -1)
    return img


@pytest.fixture
def counter():
    return BayCounter(BAY, counter_frame())


@pytest.mark.parametrize("centers,expected", [
    ([], 0),
    ([(150, 150)], 1),
    ([(150, 150), (450, 300)], 2),
    ([(120, 120), (320, 120), (520, 120), (320, 350)], 4),
])
def test_counts_separated_plates(counter, centers, expected):
    assert counter.count(with_plates(centers)).count == expected


def test_touching_plates_split(counter):
    pc = counter.count(with_plates([(250, 240), (368, 240)]))  # 2 plates touching edge-to-edge
    assert pc.count == 2
    assert pc.confidence < 1.0


def test_lighting_shift_is_not_a_plate(counter):
    brighter = cv2.convertScaleAbs(counter_frame(), alpha=1.3, beta=0)
    assert counter.count(brighter).count == 0
    assert counter.count(cv2.convertScaleAbs(with_plates([(200, 200)]), alpha=1.2)).count == 1


def test_small_debris_ignored(counter):
    img = counter_frame()
    cv2.circle(img, (300, 300), 10, (235, 235, 235), -1)
    assert counter.count(img).count == 0


def test_plate_outside_bay_ignored():
    small = BayConfig(id="B", polygon=[(0, 0), (300, 0), (300, 480), (0, 480)],
                      min_plate_area_px=4000, max_plate_area_px=40000)
    c = BayCounter(small, counter_frame())
    assert c.count(with_plates([(480, 240)])).count == 0


# ---- tracker ----

def test_tracker_debounce():
    t = BayTracker(debounce_s=0.8)
    assert t.update(0.0, 1, 0.9, False).change is None
    assert t.update(0.5, 1, 0.9, False).change is None
    ch = t.update(0.9, 1, 0.9, False).change
    assert ch and ch.kind == "arrived" and (ch.before, ch.after) == (0, 1)
    assert t.update(1.0, 1, 0.9, False).change is None


def test_tracker_flicker_does_not_emit():
    t = BayTracker(debounce_s=0.8)
    for i, raw in enumerate([1, 0, 1, 0, 1, 0]):
        assert t.update(i * 0.3, raw, 0.9, False).change is None
    assert t.stable_count == 0


def test_tracker_suppresses_during_motion_and_reports_occlusion():
    t = BayTracker(debounce_s=0.8, occlusion_timeout_s=6)
    for i in range(10):
        assert t.update(i * 0.5, 1, 0.9, True).change is None  # hand in bay
    u = t.update(7.0, 1, 0.9, True)
    assert u.occluded_timeout
    assert not t.update(7.5, 1, 0.9, True).occluded_timeout  # fires once
    assert t.update(8.0, 1, 0.9, False).occlusion_cleared
    t.update(8.5, 1, 0.9, False)
    ch = t.update(9.0, 1, 0.9, False).change
    assert ch and ch.kind == "arrived"


def test_two_plates_then_removal():
    t = BayTracker(debounce_s=0.5)
    changes = []
    seq = [1] * 4 + [2] * 4 + [0] * 4
    for i, raw in enumerate(seq):
        u = t.update(i * 0.3, raw, 0.9, False)
        if u.change:
            changes.append((u.change.kind, u.change.before, u.change.after))
    assert changes == [("arrived", 0, 1), ("arrived", 1, 2), ("removed", 2, 0)]
