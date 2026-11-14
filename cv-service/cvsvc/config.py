"""Pydantic models for config/cv.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml
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


class PlatingConfig(BaseModel):
    camera: str = "plating_cam"
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
