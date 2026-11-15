"""Deterministic structured-menu import; raw inputs are not retained.

JSON supports canonical documents or items with names and optional fields.
CSV/plain text are deliberately bounded formats, not arbitrary OCR extraction.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from typing import Literal

from pydantic import Field

from app.mvp.menu import MenuDocument, MenuModel, names, normalize


class MenuPrepareRequest(MenuModel):
    content: str = Field(min_length=1, max_length=100_000)
    media_type: Literal["application/json", "text/csv", "text/plain"] = (
        "application/json"
    )
    name: str = Field(default="Imported menu", min_length=1, max_length=200)


class MenuSearchRequest(MenuModel):
    text: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    menu_revision: str | None = None
    limit: int = Field(default=5, ge=1, le=20)


def _id(value):
    clean = normalize(value)
    slug = re.sub(r"[^a-z0-9]+", "_", clean).strip("_")[:60] or "item"
    # Hash preserves distinct Unicode names and avoids truncation collisions.
    return f"{slug}_{hashlib.sha256(clean.encode()).hexdigest()[:10]}"


def parse_menu(request: MenuPrepareRequest) -> MenuDocument:
    if request.media_type == "application/json":
        document = json.loads(request.content)
        if isinstance(document, list):
            document = {"items": document}
        if not isinstance(document, dict):
            raise ValueError("JSON must be a menu object or an item list")
    elif request.media_type == "text/csv":
        reader = csv.DictReader(io.StringIO(request.content))
        allowed = {"id", "name", "description", "category", "price_cents", "aliases"}
        if not reader.fieldnames or "name" not in reader.fieldnames:
            raise ValueError("CSV requires a name header")
        if (
            len(set(reader.fieldnames)) != len(reader.fieldnames)
            or set(reader.fieldnames) - allowed
        ):
            raise ValueError("CSV has duplicate or unsupported headers")
        rows = []
        for row in reader:
            if None in row:
                raise ValueError("CSV row has more values than headers")
            entry = {
                key: value.strip()
                for key, value in row.items()
                if value and value.strip()
            }
            if "aliases" in entry:
                entry["aliases"] = [
                    part.strip() for part in entry["aliases"].split(";") if part.strip()
                ]
            if "price_cents" in entry:
                try:
                    entry["price_cents"] = int(entry["price_cents"])
                except ValueError as exc:
                    raise ValueError("CSV price_cents must be integer cents") from exc
            rows.append(entry)
        document = {"items": rows}
    else:
        # Every nonblank line is an item: Name OR Name | Description. Headings,
        # prices and kitchen data are not inferred from unstructured prose.
        rows = []
        for line in request.content.splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) > 2:
                raise ValueError("Text lines use Name or Name | Description")
            rows.append(
                {
                    "name": parts[0].strip(),
                    "description": parts[1].strip() if len(parts) == 2 else None,
                }
            )
        document = {"items": rows}
    document.setdefault("name", request.name)
    if not isinstance(document["name"], str):
        raise ValueError("Menu name must be text")
    document.setdefault("id", _id(document["name"]))
    if not isinstance(document.get("items"), list):
        raise ValueError("Menu items must be a list")
    if not 1 <= len(document["items"]) <= 500:
        raise ValueError("Import requires between 1 and 500 items")
    items = []
    for value in document["items"]:
        if isinstance(value, str):
            value = {"name": value}
        if not isinstance(value, dict) or not isinstance(value.get("name"), str):
            raise ValueError("Each item requires a name")
        entry = dict(value)
        entry.setdefault("id", _id(entry["name"]))
        items.append(entry)
    return MenuDocument.model_validate({**document, "items": items})


def review_warnings(menu):
    aliases = {}
    for item in menu.items:
        for alias in names(item):
            aliases.setdefault(alias, set()).add(item.id)
    return [
        {"code": "ambiguous_item_alias", "alias": alias, "candidates": sorted(ids)}
        for alias, ids in sorted(aliases.items())
        if len(ids) > 1
    ]
