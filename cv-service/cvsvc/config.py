"""Pydantic models for config/cv.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml
from typing import Literal

from pydantic import BaseModel, Field

Point = tuple[int, int]


class CameraConfig(BaseModel):
    # int = webcam index; str = RTSP/HTTP URL, video file path, or image directory
    source: int | str = 0
    fps_target: int = 15
    resolution: tuple[int, int] = (1280, 720)
    loop: bool = False  # loop video files (useful for replay/demo)


class SlotGrid(BaseModel):
    rows: int = 1
    cols: int = 1


class ZoneConfig(BaseModel):
    id: str
    ingredient: str
    polygon: list[Point] = Field(default_factory=list)
    slots: SlotGrid = Field(default_factory=SlotGrid)
    diff_threshold: int = 28
    occupied_min_fraction: float = 0.35

    @property
    def max_count(self) -> int:
        return self.slots.rows * self.slots.cols


class IngredientConfig(BaseModel):
    camera: str = "ingredient_cam"
    # trips: detect a hand reaching into a zone; the backend owns counts (default)
    # slots: count portions with the slot grid (CV_SPEC 6.2)
    mode: Literal["trips", "slots"] = "trips"
    min_trip_s: float = 0.25        # shorter motion bursts are noise
    trip_settle_s: float = 0.6      # no motion this long ends a trip
    body_motion_fraction: float = 0.25  # share of the frame occupied by something new => a person in front, not a reach
    body_hold_s: float = 1.0        # keep treating motion as "body" this long after the person leaves
    # trip_detector: hands  = a detected hand dwelling in the zone (MediaPipe); robust to bodies/passers-by
    #                motion = motion in the zone polygon (no extra dependency; fixed overhead cameras)
    trip_detector: Literal["hands", "motion"] = "motion"
    hand_model_path: str = "models/hand_landmarker.task"
    hand_dwell_s: float = 0.35      # hand must stay in the zone this long to count as a trip
    hand_max_size_px: float = 200   # ignore hands this large (right in front of the lens, not at the shelf)
    settle_s: float = 1.0
    occlusion_timeout_s: float = 6.0
    snapshot_interval_s: float = 10
    active_ticket_ttl_s: float = 120
    large_delta_limit: int = 4
    motion_min_area_px: int = 800
    zones: list[ZoneConfig] = Field(default_factory=list)


class BayConfig(BaseModel):
    id: str
    polygon: list[Point] = Field(default_factory=list)
    min_plate_area_px: int = 6000
    max_plate_area_px: int = 60000
    min_circularity: float = 0.6
    diff_threshold: int = 30
    # diff: foreground = difference vs the empty reference (CV_SPEC 7.2)
    # white: foreground = bright, low-saturation pixels (white plates on a coloured counter);
    #        independent of the reference, so exposure drift and wood grain don't matter
    detector: Literal["diff", "white"] = "diff"
    white_s_max: int = 80      # absolute bounds ...
    white_v_min: int = 130
    white_s_rel: float = 0.7   # ... and relative to the bay's median (the counter), which
    white_v_rel: float = 1.1   # survives the camera's auto white balance / exposure shifts
    min_solidity: float = 0.9  # area / convex hull: plates are solid, wood-grain noise is not


class PlatingConfig(BaseModel):
    camera: str = "plating_cam"
    # circles: plates found by shape (Hough circles) once per frame, assigned to the bay holding
    #          their centre; independent of plate pattern and counter colour (recommended)
    # bays:    per-bay foreground detector (each bay's `detector`: diff | white)
    detector: Literal["circles", "bays"] = "bays"
    plate_min_radius_px: int = 90
    plate_max_radius_px: int = 260
    circle_quality: float = 0.75
    debounce_s: float = 0.8
    snapshot_interval_s: float = 10
    max_plates_per_bay: int = 4
    occlusion_timeout_s: float = 6.0
    motion_min_area_px: int = 1500
    bays: list[BayConfig] = Field(default_factory=list)


class HealthConfig(BaseModel):
    lost_after_s: float = 2.0
    dark_threshold: float = 25.0
    blur_threshold: float = 15.0
    big_change_fraction: float = 0.7
    big_change_hold_s: float = 1.5
    degraded_light_shift: float = 0.25
    degraded_focus_drop: float = 0.40
    recovery_wait_s: float = 2.0
    allow_rebaseline: bool = True  # legacy only; canonical v2 disables automatic scene acceptance
    rebaseline_s: float = 5.0  # view "blocked" but perfectly still this long => the scene was rearranged; accept it
    warmup_s: float = 2.0  # ignore the first seconds of frames (auto-exposure settling)
    heartbeat_s: float = 5.0


class SinksConfig(BaseModel):
    stdout: bool = False
    backend_url: str | None = None  # e.g. http://localhost:8002/cv/events
    outbox_path: str = "logs/outbox.jsonl"


class CVConfig(BaseModel):
    cameras: dict[str, CameraConfig] = Field(default_factory=dict)
    ingredient: IngredientConfig = Field(default_factory=IngredientConfig)
    plating: PlatingConfig = Field(default_factory=PlatingConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)
    sinks: SinksConfig = Field(default_factory=SinksConfig)
    events_log_path: str = "logs/events.jsonl"
    calibration_dir: str = "config/calibration"


def load_config(path: str | Path) -> CVConfig:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return CVConfig.model_validate(data)


def save_config(cfg: CVConfig, path: str | Path) -> None:
    Path(path).write_text(yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False))
