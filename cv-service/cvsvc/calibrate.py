"""Interactive calibration (CV_SPEC.md section 10).

    python -m cvsvc.calibrate --camera ingredient_cam [--config config/cv.yaml]

Keys (in the OpenCV window):
  left-click   add a polygon corner for the current zone/bay (4 corners, clockwise from top-left)
  u            undo last corner
  c            clear current polygon
  n / p        next / previous zone or bay
  + / -        (ingredient zones) add / remove a slot column;  ] / [  add / remove a slot row
  r            capture the EMPTY reference frame now (zones/bays must be empty)
  s            save polygons + slot grids to the config file
  q / Esc      quit (unsaved changes are discarded)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from cvsvc.config import load_config, save_config
from cvsvc.pipeline import reference_path
from cvsvc.sources import FrameSource

WIN = "dig-in calibrate"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--camera", required=True)
    ap.add_argument("--config", default="config/cv.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.camera not in cfg.cameras:
        raise SystemExit(f"camera {args.camera!r} not in {args.config}")
    cam = cfg.cameras[args.camera]
    items: list = []
    if cfg.ingredient.camera == args.camera:
        items += cfg.ingredient.zones
    if cfg.plating.camera == args.camera:
        items += cfg.plating.bays
    if not items:
        raise SystemExit(f"no zones or bays use {args.camera}; add them to the config first")

    src = FrameSource(cam.source, tuple(cam.resolution), cam.fps_target, loop=True)
    idx = 0
    points: dict[str, list[tuple[int, int]]] = {it.id: [tuple(p) for p in it.polygon] for it in items}
    status = "click 4 corners clockwise from top-left"

    def on_mouse(event, x, y, *_):
        nonlocal status
        if event == cv2.EVENT_LBUTTONDOWN:
            pts = points[items[idx].id]
            if len(pts) >= 4:
                pts.clear()
            pts.append((x, y))
            status = f"{items[idx].id}: {len(pts)}/4 corners"

    cv2.namedWindow(WIN)
    cv2.setMouseCallback(WIN, on_mouse)
    frame = None
    while True:
        f = src.read()
        if f is not None:
            frame = f
        if frame is None:
            if cv2.waitKey(100) & 0xFF in (ord("q"), 27):
                break
            continue
        img = frame.copy()
        for i, it in enumerate(items):
            pts = points[it.id]
            color = (0, 200, 255) if i == idx else (120, 200, 120)
            for p in pts:
                cv2.circle(img, p, 4, color, -1)
            if len(pts) >= 2:
                cv2.polylines(img, [np.array(pts, np.int32)], len(pts) == 4, color, 2)
            if len(pts) == 4 and hasattr(it, "slots"):
                _draw_grid(img, pts, it.slots.rows, it.slots.cols, color)
            if pts:
                label = it.id + (f" {it.slots.rows}x{it.slots.cols}" if hasattr(it, "slots") else "")
                cv2.putText(img, label, (pts[0][0], pts[0][1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        cur = items[idx]
        kind = "zone" if hasattr(cur, "slots") else "bay"
        cv2.rectangle(img, (0, 0), (img.shape[1], 30), (0, 0, 0), -1)
        cv2.putText(img, f"[{kind} {cur.id}] {status}  | n/p next/prev  r ref  s save  q quit",
                    (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.imshow(WIN, img)
        k = cv2.waitKey(30) & 0xFF
        if k in (ord("q"), 27):
            break
        if k == ord("n"):
            idx = (idx + 1) % len(items)
            status = f"{items[idx].id}: {len(points[items[idx].id])}/4 corners"
        elif k == ord("p"):
            idx = (idx - 1) % len(items)
            status = f"{items[idx].id}: {len(points[items[idx].id])}/4 corners"
        elif k == ord("u") and points[cur.id]:
            points[cur.id].pop()
        elif k == ord("c"):
            points[cur.id].clear()
        elif kind == "zone" and k in (ord("+"), ord("=")):
            cur.slots.cols += 1
        elif kind == "zone" and k == ord("-") and cur.slots.cols > 1:
            cur.slots.cols -= 1
        elif kind == "zone" and k == ord("]"):
            cur.slots.rows += 1
        elif kind == "zone" and k == ord("[") and cur.slots.rows > 1:
            cur.slots.rows -= 1
        elif k == ord("r"):
            p = reference_path(cfg, args.camera)
            p.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(p), frame)
            status = f"empty reference saved to {p}"
        elif k == ord("s"):
            bad = [it.id for it in items if len(points[it.id]) != 4]
            if bad:
                status = f"need 4 corners for: {', '.join(bad)}"
                continue
            for it in items:
                it.polygon = points[it.id]
            save_config(cfg, args.config)
            status = f"saved to {args.config}" + ("" if reference_path(cfg, args.camera).exists()
                                                  else "  (no reference yet: empty the area and press r)")
    src.release()
    cv2.destroyAllWindows()


def _draw_grid(img, pts, rows, cols, color) -> None:
    src = np.array([(0, 0), (1, 0), (1, 1), (0, 1)], np.float32)
    M = cv2.getPerspectiveTransform(src, np.array(pts, np.float32))
    for c in range(1, cols):
        line = cv2.perspectiveTransform(np.array([[(c / cols, 0), (c / cols, 1)]], np.float32), M)[0]
        cv2.line(img, tuple(map(int, line[0])), tuple(map(int, line[1])), color, 1)
    for r in range(1, rows):
        line = cv2.perspectiveTransform(np.array([[(0, r / rows), (1, r / rows)]], np.float32), M)[0]
        cv2.line(img, tuple(map(int, line[0])), tuple(map(int, line[1])), color, 1)


if __name__ == "__main__":
    main()
