"""Canonical MVP menu contract, deterministic matching, and importer boundary.

Unknown kitchen fields remain None. Every new consumer imports these models;
changing an alias/menu fixture does not require editing parser or domain code.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MenuModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )


class Modifier(MenuModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    aliases: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=32
    )


class RecipeIngredient(MenuModel):
    ingredient: str = Field(min_length=1)
    qty: float = Field(gt=0)
    zone_id: str | None = None


class MenuItem(MenuModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    aliases: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=32
    )
    modifiers: list[Modifier] = Field(default_factory=list)
    description: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=200)
    price_cents: int | None = Field(default=None, ge=0)
    call_out_name: str | None = None
    station: str | None = None
    typical_minutes: float | None = Field(default=None, gt=0)
    recipe: list[RecipeIngredient] | None = None

    @model_validator(mode="after")
    def unique_modifiers(self):
        if not normalize(self.name):
            raise ValueError("Item name must contain letters or numbers")
        if len({m.id for m in self.modifiers}) != len(self.modifiers):
            raise ValueError("Modifier IDs must be unique per item")
        return self


class MenuDocument(MenuModel):
    schema_version: Literal[2] = 2
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    items: list[MenuItem] = Field(min_length=1, max_length=500)
    ingredient_zones: dict[str, str | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_items(self):
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("Menu item IDs must be unique")
        return self

    def item(self, item_id: str) -> MenuItem | None:
        return next((item for item in self.items if item.id == item_id), None)


DEFAULT_MENU_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "menus" / "starter.json"
)


def load_menu(path: str | Path | None = None) -> MenuDocument:
    selected = Path(path or os.environ.get("DIG_IN_MENU_PATH") or DEFAULT_MENU_PATH)
    return MenuDocument.model_validate_json(selected.read_text())


def normalize(text: str) -> str:
    return " ".join(
        re.sub(
            r"[^\w\s]", " ", text.lower().replace("&", " and ").replace("_", " ")
        ).split()
    )


def names(entity: MenuItem | Modifier) -> set[str]:
    return {
        normalize(value)
        for value in [entity.id, entity.name, *entity.aliases]
        if normalize(value)
    }


def _occurrences(text: str, aliases: set[str]):
    return [
        (match.start(), match.end())
        for alias in aliases
        for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text)
    ]


def match_menu(
    menu: MenuDocument, text: str, *, suggest: Callable[[str], list[str]] | None = None
) -> dict:
    """Match a single item clause; return candidates/flags instead of fuzzy guesses.

    A longer exact alias takes precedence over an overlapping shorter alias.
    Independent or equal-length matches across items stay ambiguous.
    """
    clean = normalize(text)
    matches = [
        (item.id, start, end)
        for item in menu.items
        for start, end in _occurrences(clean, names(item))
    ]
    matches = [
        entry
        for entry in matches
        if not any(
            other[1] <= entry[1]
            and other[2] >= entry[2]
            and other[2] - other[1] > entry[2] - entry[1]
            for other in matches
        )
    ]
    candidates = sorted({entry[0] for entry in matches})
    if len(candidates) != 1:
        if not candidates:
            # Token overlap suggests candidates only; it never selects one.
            words = set(clean.split())
            candidates = sorted(
                item.id
                for item in menu.items
                if any(words & set(alias.split()) for alias in names(item))
            )
        if not matches and suggest is not None:
            candidates = list(dict.fromkeys([*candidates, *suggest(text)]))
        return {
            "status": "ambiguous" if matches else "unknown",
            "menu_id": None,
            "modifiers": [],
            "candidates": candidates,
            "flags": [
                {
                    "code": "ambiguous_item" if matches else "unknown_item",
                    "message": "Choose a menu item explicitly; no item was guessed.",
                    "candidates": candidates,
                }
            ],
            "unmatched_terms": clean.split(),
        }
    item = menu.item(candidates[0])
    assert item is not None
    spans = [(a, b) for key, a, b in matches if key == item.id]
    modifier_matches = [
        (modifier.id, a, b)
        for modifier in item.modifiers
        for a, b in _occurrences(clean, names(modifier))
    ]
    modifier_matches = [
        entry
        for entry in modifier_matches
        if not any(
            other[1] <= entry[1]
            and other[2] >= entry[2]
            and other[2] - other[1] > entry[2] - entry[1]
            for other in modifier_matches
        )
    ]
    ambiguous_modifiers = {
        entry[0]
        for entry in modifier_matches
        if any(
            other[0] != entry[0] and other[1:] == entry[1:]
            for other in modifier_matches
        )
    }
    modifiers = sorted({entry[0] for entry in modifier_matches} - ambiguous_modifiers)
    spans += [
        (a, b) for key, a, b in modifier_matches if key not in ambiguous_modifiers
    ]
    chars = list(clean)
    for start, end in spans:
        chars[start:end] = " " * (end - start)
    remainder = [
        word
        for word in "".join(chars).split()
        if word not in {"please", "with", "and", "a", "an", "the"}
    ]
    flags = []
    if ambiguous_modifiers:
        flags.append(
            {
                "code": "ambiguous_modifier",
                "message": "Choose the modifier explicitly.",
                "candidates": sorted(ambiguous_modifiers),
            }
        )
    if remainder:
        flags.append(
            {
                "code": "unknown_terms",
                "message": "Some words are not configured item/modifier aliases; review them manually.",
                "candidates": [],
            }
        )
    return {
        "status": "matched" if not flags else "unknown",
        "menu_id": item.id,
        "modifiers": modifiers,
        "candidates": [item.id],
        "flags": flags,
        "unmatched_terms": remainder,
    }


class MenuImporter(Protocol):
    """Future importer creates a review candidate, never silently activates a menu."""

    def propose(self, content: bytes, media_type: str) -> MenuDocument: ...


class UnconfiguredMenuImporter:
    def propose(self, content: bytes, media_type: str) -> MenuDocument:
        raise NotImplementedError(
            "PDF/photo/text-model import is adapter-only; use a reviewed canonical JSON menu"
        )


def import_status(menu: MenuDocument) -> dict:
    missing = {}
    for item in menu.items:
        fields = [
            field
            for field in ("station", "call_out_name", "typical_minutes", "recipe")
            if getattr(item, field) is None
        ]
        if item.recipe is not None and any(
            (entry.zone_id or menu.ingredient_zones.get(entry.ingredient)) is None
            for entry in item.recipe
        ):
            fields.append("ingredient_zone_mapping")
        if fields:
            missing[item.id] = fields
    return {
        "mode": "structured_review",
        "live_import_available": False,
        "requires_human_review": True,
        "missing_kitchen_fields": missing,
        "structured_import_available": True,
        "supported_media_types": ["application/json", "text/csv", "text/plain"],
        "message": "Prepare structured JSON/CSV/item-per-line text, review, then activate. PDF/photo local extraction readiness is at /api/v2/menu/extraction-status. Missing kitchen data stays unknown.",
    }
