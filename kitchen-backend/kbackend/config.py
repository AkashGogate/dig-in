from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class RecipeLine(BaseModel):
    zone: str
    qty: int


class ZoneSeed(BaseModel):
    ingredient: str
    on_hand: int = 0


class Settings(BaseModel):
    cv_base_url: str = "http://localhost:8001"
    event_source: Literal["http", "ws"] = "http"
    readiness_mode: Literal["auto", "confirm"] = "auto"
    auto_serve_on_removal: bool = True
    cv_stale_after_s: float = 10
    allocate_on: Literal["submit", "cooking_complete"] = "submit"
    bays: list[str] = Field(default_factory=lambda: ["A", "B", "C"])
    db_path: str = "data/kitchen.db"
    schema_path: str = "../schema/events.schema.json"
    zone_count_tolerance: int = 0
    zones: dict[str, ZoneSeed] = Field(default_factory=dict)
    recipes: dict[str, list[RecipeLine]] = Field(default_factory=dict)
    push_context: bool = True  # tests turn this off


def load_settings(path: str | Path) -> Settings:
    p = Path(path)
    if not p.exists():
        return Settings()
    s = Settings.model_validate(yaml.safe_load(p.read_text()) or {})
    # resolve relative paths against the config file's directory
    base = p.resolve().parent
    if not Path(s.schema_path).is_absolute():
        s.schema_path = str((base / s.schema_path).resolve())
    if s.db_path != ":memory:" and not Path(s.db_path).is_absolute():
        s.db_path = str((base / s.db_path).resolve())
    return s
