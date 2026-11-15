"""One simulation: heard text -> the real v2 voice path -> observed result.

Server cases go through Restaurant.capture_voice (the same command the browser
sends), so flags the domain adds (seat_unknown, dietary) count. Kitchen cases
seed real tickets, send kitchen_voice as a cook session and diff the state,
so `wrong` means the domain acknowledged/started the wrong thing.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from uuid import uuid4

from app.mvp.contracts import Command, Table
from app.mvp.domain import Restaurant
from app.mvp.menu import MenuDocument
from app.mvp.menu_embeddings import LocalEmbeddings
from app.mvp.voice import parse_order

LINE_KEYS = ("menu_id", "quantity", "modifiers", "seat", "requests")
# The demo fixture seeds tables 1-3; eval scripts use tables up to 9.
EVAL_TABLES = [str(n) for n in range(1, 10)]


@contextmanager
def _isolated_env(live=False):
    """Run domain checks without provider I/O, then restore every demo toggle."""
    keys = ("DIG_IN_REQUIRE_DIETARY_CHECK", "DIG_IN_VOICE_LIVE", "DEEPGRAM_API_KEY")
    saved = {key: os.environ.get(key) for key in keys}
    os.environ.pop("DIG_IN_REQUIRE_DIETARY_CHECK", None)
    os.environ["DIG_IN_VOICE_LIVE"] = "1" if live else "0"
    # Only enable the domain's live-mode validation. No simulation opens STT.
    os.environ["DEEPGRAM_API_KEY"] = "eval-no-provider-call"
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _restaurant(menu: MenuDocument) -> tuple[Restaurant, str, str]:
    restaurant = Restaurant(menu=menu, embedding_provider=LocalEmbeddings())
    for table_id in EVAL_TABLES:
        restaurant.state.tables.setdefault(table_id, Table(id=table_id))
    server = restaurant.session("server-1")["session_id"]
    cook = restaurant.session("cook-1")["session_id"]
    return restaurant, server, cook


def _run(restaurant: Restaurant, session: str, payload: dict, source: str) -> dict:
    command = Command(
        event_id=str(uuid4()),
        source=source,
        payload=payload,
        run_id="dig-in-eval",
        simulated=True,
    )
    return restaurant.execute(command, session)["result"]


def _seed(restaurant, server, cook, context: list[dict]) -> dict[str, str]:
    labels = {}
    for ticket in context:
        order_id = _run(
            restaurant,
            server,
            {"action": "start_order", "table_id": ticket["table_id"]},
            "tap",
        )["order_id"]
        lines = [
            {
                "id": f"line-{n}",
                "menu_id": line["menu_id"],
                "quantity": line["quantity"],
            }
            for n, line in enumerate(ticket["lines"])
        ]
        _run(
            restaurant,
            server,
            {
                "action": "edit_draft",
                "order_id": order_id,
                "revision": 1,
                "table_id": ticket["table_id"],
                "lines": lines,
            },
            "tap",
        )
        _run(
            restaurant,
            server,
            {
                "action": "confirm_send",
                "order_id": order_id,
                "revision": 2,
                "human_confirmed": True,
            },
            "tap",
        )
        if ticket["state"] == "acknowledged":
            _run(
                restaurant, cook, {"action": "acknowledge", "order_id": order_id}, "tap"
            )
        labels[order_id] = ticket["label"]
    return labels


def _effects(restaurant, labels: dict[str, str]) -> tuple[set[str], dict[str, str]]:
    state = restaurant.state
    acknowledged = {
        labels[o.id]
        for o in state.orders.values()
        if o.id in labels and o.acknowledged_at
    }
    started = {
        d.id: f"{labels[d.order_id]}:{d.menu_id}"
        for d in state.dishes.values()
        if d.order_id in labels and d.started_at
    }
    return acknowledged, started


def observe_server(
    case: dict, text: str, menu: MenuDocument, *, live=False, confidence=None
) -> dict:
    with _isolated_env(live):
        restaurant, server, _ = _restaurant(menu)
        order_id = _run(
            restaurant,
            server,
            {"action": "start_order", "table_id": case["selected_table_id"]},
            "tap",
        )["order_id"]
        _run(
            restaurant,
            server,
            {
                "action": "capture_voice",
                "order_id": order_id,
                "revision": 1,
                "text": text,
                "capture_mode": "live_voice" if live else "mock_voice",
                "stt_confidence": confidence,
            },
            "voice",
        )
    order = restaurant.state.orders[order_id]
    return {
        "table_id": parse_order(menu, text, case["selected_table_id"])["table_id"],
        "lines": [line.model_dump(include=set(LINE_KEYS)) for line in order.lines],
        "flag_codes": sorted(f.code for f in order.flags),
        "candidates": sorted({c for f in order.flags for c in f.candidates}),
        "dietary_check": order.dietary_check,
    }


def observe_kitchen(
    case: dict, text: str, menu: MenuDocument, *, live=False, confidence=None
) -> dict:
    with _isolated_env(live):
        restaurant, server, cook = _restaurant(menu)
        labels = _seed(restaurant, server, cook, case.get("context", []))
        before = _effects(restaurant, labels)
        result = _run(
            restaurant,
            cook,
            {
                "action": "kitchen_voice",
                "text": text,
                "capture_mode": "live_voice" if live else "mock_voice",
                "stt_confidence": confidence,
            },
            "voice",
        )
        after = _effects(restaurant, labels)
    flags = result.get("flags") or []
    return {
        "acknowledged": sorted(after[0] - before[0]),
        "started": sorted(
            label for key, label in after[1].items() if key not in before[1]
        ),
        "candidates": sorted({c for f in flags for c in f.get("candidates", [])}),
        "asked": bool(flags),
    }


def observe(
    case: dict, text: str, menu: MenuDocument, *, live=False, confidence=None
) -> dict:
    if case["flow"] == "kitchen":
        return observe_kitchen(case, text, menu, live=live, confidence=confidence)
    return observe_server(case, text, menu, live=live, confidence=confidence)
