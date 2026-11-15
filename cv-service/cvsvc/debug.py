"""Debug overlay (CV_SPEC.md section 10): polygons coloured by state, slot grid, bay labels,
counts, camera-state banner, FPS. Served as MJPEG by the API."""
from __future__ import annotations

import cv2
import numpy as np

GREEN, AMBER, RED, GREY, WHITE = (60, 200, 60), (0, 190, 255), (40, 40, 230), (150, 150, 150), (255, 255, 255)
STATE_COLOR = {"stable": GREEN, "active": AMBER, "settling": AMBER, "occluded": RED, "pending": RED}
CAM_COLOR = {"ok": GREEN, "degraded": AMBER, "obstructed": RED, "lost": RED}


def _label(img: np.ndarray, text: str, org: tuple[int, int], color=WHITE, scale: float = 0.6) -> None:
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def draw_zone(img, polygon, state: str, zone_id: str, ingredient: str, count: int,
              slot_polys: list[np.ndarray], occupied: list[bool]) -> None:
    color = STATE_COLOR.get(state, GREY)
    for poly, occ in zip(slot_polys, occupied):
        if occ:
            cv2.fillPoly(img, [poly], color)
        cv2.polylines(img, [poly], True, GREY, 1)
    cv2.polylines(img, [np.array(polygon, np.int32)], True, color, 2)
    x, y = polygon[0]
    _label(img, f"{zone_id} {ingredient}: {count}  [{state}]", (x, max(18, y - 8)), color)


def draw_trip_zone(img, polygon, state: str, zone_id: str, ingredient: str, trips: int) -> None:
    color = STATE_COLOR.get(state, GREY)
    pts = np.array(polygon, np.int32)
    if state == "active":
        overlay = img.copy()
        cv2.fillPoly(overlay, [pts], color)
        cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)
    cv2.polylines(img, [pts], True, color, 2)
    x, y = polygon[0]
    _label(img, f"{zone_id} {ingredient}  trips: {trips}  [{state}]", (x, max(18, y - 8)), color)


def draw_hand(img, points, tip) -> None:
    for x, y in points.astype(int):
        cv2.circle(img, (int(x), int(y)), 3, (255, 0, 255), -1)
    cv2.circle(img, (int(tip[0]), int(tip[1])), 8, (255, 0, 255), 2)


def draw_bay(img, polygon, state: str, bay_id: str, count: int, assignment, contours) -> None:
    color = STATE_COLOR.get(state, GREY)
    cv2.polylines(img, [np.array(polygon, np.int32)], True, color, 2)
    if contours:
        cv2.drawContours(img, contours, -1, (255, 200, 0), 2)
    x, y = polygon[0]
    y = max(y, 32)  # keep the label below the camera banner
    label = f"Bay {bay_id}"
    if assignment is not None:
        label += f" - table {assignment.table}, {assignment.course}" if assignment.table else f" - {assignment.ticket_id}"
    _label(img, label, (x + 4, y + 22), color, 0.65)
    _label(img, f"plates: {count}" + (f"/{assignment.expected_plates}" if assignment and assignment.expected_plates else ""),
           (x + 4, y + 46), WHITE)


def draw_banner(img, camera_id: str, state: str, reason: str | None, fps: float) -> None:
    color = CAM_COLOR.get(state, GREY)
    cv2.rectangle(img, (0, 0), (img.shape[1], 28), (0, 0, 0), -1)
    _label(img, f"{camera_id}  {state.upper()}" + (f" ({reason})" if reason else "") + f"   {fps:.1f} fps",
           (8, 20), color, 0.6)
    if state in ("obstructed", "lost"):
        cv2.rectangle(img, (0, 0), (img.shape[1] - 1, img.shape[0] - 1), RED, 6)


def placeholder(camera_id: str, text: str = "no frame") -> np.ndarray:
    img = np.zeros((360, 640, 3), np.uint8)
    _label(img, f"{camera_id}: {text}", (20, 180), RED, 0.8)
    return img


def encode_jpeg(img: np.ndarray, quality: int = 70) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else b""
