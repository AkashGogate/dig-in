import cv2
import numpy as np

from cvsvc.plating.circles import PlateFinder, assign_to_bays

W, H = 1280, 720


def textured(seed=0, base=(60, 50, 45)):
    rng = np.random.default_rng(seed)
    img = np.full((H, W, 3), base, np.uint8)
    img = cv2.add(img, rng.integers(0, 40, (H, W, 3), dtype=np.uint8))  # fabric/wood-like texture
    for _ in range(80):  # grain lines
        x = int(rng.integers(0, W))
        cv2.line(img, (x, 0), (x + int(rng.integers(-40, 40)), H), tuple(int(v) for v in rng.integers(30, 90, 3)), 2)
    return img


def plate(img, c, r, patterned=False):
    cv2.circle(img, c, r, (235, 235, 235), -1)
    cv2.circle(img, c, int(r * 0.78), (215, 215, 215), 3)  # inner rim ring
    if patterned:
        for a in range(0, 360, 20):
            t = np.deg2rad(a)
            p = (int(c[0] + 0.88 * r * np.cos(t)), int(c[1] + 0.88 * r * np.sin(t)))
            cv2.ellipse(img, p, (12, 6), a, 0, 360, (150, 60, 20), -1)  # blue leaf pattern on the rim
    return img


BAYS = {"A": np.array([(0, 5), (400, 5), (400, 680), (0, 680)], np.int32),
        "B": np.array([(440, 5), (840, 5), (840, 680), (440, 680)], np.int32),
        "C": np.array([(880, 5), (1280, 5), (1280, 680), (880, 680)], np.int32)}


def counts(img):
    by = assign_to_bays(PlateFinder().find(img), BAYS)
    return {k: len(v) for k, v in by.items()}


def test_empty_textured_counter_has_no_plates():
    assert counts(textured(1)) == {"A": 0, "B": 0, "C": 0}


def test_plain_and_patterned_plates_one_per_bay():
    img = textured(2)
    plate(img, (200, 400), 150)
    plate(img, (640, 300), 140, patterned=True)
    plate(img, (1080, 420), 160, patterned=True)
    assert counts(img) == {"A": 1, "B": 1, "C": 1}


def test_two_plates_in_one_bay_and_overhang_assigned_by_centre():
    img = textured(3, base=(140, 170, 200))  # light wood
    plate(img, (640, 170), 120)
    plate(img, (640, 450), 120)
    plate(img, (380, 400), 150)  # hangs over A's right edge; centre is in A
    assert counts(img) == {"A": 1, "B": 2, "C": 0}
