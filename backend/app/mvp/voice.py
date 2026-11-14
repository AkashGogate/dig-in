"""Constrained menu-driven voice parsing. Inputs are ephemeral, never logged.

No transcription provider, noisy-room guarantee or speaker authentication is
implemented here. A provider adapter can return text to these same functions.
"""

from __future__ import annotations

import re
from typing import Protocol

from app.mvp.menu import MenuDocument, match_menu, names, normalize

NUMBER_WORDS = {
    word: n
    for n, word in enumerate(
        (
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
        ),
        start=1,
    )
}
NUMBER = r"(?:\d+|" + "|".join(NUMBER_WORDS) + r")"


def _clauses(menu: MenuDocument, text: str) -> list[str]:
    # Do not split a configured name/modifier containing 'and'.
    protected = normalize(text)
    phrases = {
        alias
        for item in menu.items
        for entity in [item, *item.modifiers]
        for alias in names(entity)
        if " and " in alias
    }
    for phrase in sorted(phrases, key=len, reverse=True):
        protected = re.sub(
            r"(?<!\w)" + re.escape(phrase) + r"(?!\w)",
            lambda m: m[0].replace(" and ", " \ue000 "),
            protected,
        )
    return [
        part.replace("\ue000", "and").strip()
        for part in re.split(r"\s+and\s+", protected)
        if part.strip()
    ]


def parse_order(
    menu: MenuDocument, text: str, selected_table_id: str, *, suggest=None
) -> dict:
    table = re.match(r"^\s*table\s+(\d+)\b\s*[:,]?", text, re.IGNORECASE)
    spoken_table = table[1] if table else None
    remainder = text[table.end() :] if table else text
    flags = []
    if not table:
        flags.append(
            {
                "code": "table_required",
                "message": "Say the table number first, or use manual entry.",
                "candidates": [],
            }
        )
    mismatch = spoken_table is not None and spoken_table != selected_table_id
    if mismatch:
        flags.append(
            {
                "code": "table_mismatch",
                "message": "Spoken and selected tables differ; explicitly resolve before sending.",
                "candidates": [selected_table_id, spoken_table],
            }
        )
    lines = []
    for index, clause in enumerate(_clauses(menu, remainder)):
        number = re.match(r"^(" + NUMBER + r")\b\s*", clause)
        quantity = (
            NUMBER_WORDS.get(
                number[1], int(number[1]) if number and number[1].isdigit() else 1
            )
            if number
            else 1
        )
        if not number:
            flags.append(
                {
                    "code": "quantity_required",
                    "message": "Confirm an explicit quantity for this phrase.",
                    "candidates": [],
                    "line_index": index,
                }
            )
        if not 1 <= quantity <= 12:
            flags.append(
                {
                    "code": "invalid_quantity",
                    "message": "Quantity must be between one and twelve; edit manually.",
                    "candidates": [],
                    "line_index": index,
                }
            )
            continue
        matched = match_menu(
            menu, clause[number.end() :] if number else clause, suggest=suggest
        )
        flags.extend({**flag, "line_index": index} for flag in matched["flags"])
        if matched["menu_id"]:
            lines.append(
                {
                    "menu_id": matched["menu_id"],
                    "quantity": quantity,
                    "modifiers": matched["modifiers"],
                }
            )
    if not lines:
        flags.append(
            {
                "code": "no_items",
                "message": "No confirmed menu items found; choose items manually.",
                "candidates": [],
            }
        )
    return {
        "table_id": spoken_table,
        "lines": lines,
        "flags": flags,
        "table_mismatch": mismatch,
    }


def parse_kitchen(menu: MenuDocument, text: str) -> dict:
    clean = normalize(text)
    heard = re.fullmatch(r"heard table (\d+)", clean)
    if heard:
        return {
            "action": "acknowledge",
            "table_id": heard[1],
            "menu_id": None,
            "flags": [],
        }
    started = re.fullmatch(r"start table (\d+) (.+)", clean)
    if started:
        matched = match_menu(menu, started[2])
        return {
            "action": "start_dish"
            if matched["status"] == "matched" and not matched["modifiers"]
            else None,
            "table_id": started[1],
            "menu_id": matched["menu_id"],
            "flags": matched["flags"]
            or (
                [
                    {
                        "code": "item_only",
                        "message": "Start names one item; choose its dish unit explicitly.",
                        "candidates": matched["candidates"],
                    }
                ]
                if matched["modifiers"]
                else []
            ),
        }
    return {
        "action": None,
        "table_id": None,
        "menu_id": None,
        "flags": [
            {
                "code": "unsupported_phrase",
                "message": "Use 'Heard, table N' or 'Start table N item', or tap the action.",
                "candidates": [],
            }
        ],
    }


class Transcriber(Protocol):
    def transcribe(self, audio: bytes, content_type: str) -> str: ...


class UnconfiguredTranscriber:
    def transcribe(self, audio: bytes, content_type: str) -> str:
        raise NotImplementedError(
            "Live transcription is not configured; use the visible mock transcript or manual taps"
        )


def transcribe_discarding(
    audio: bytearray, content_type: str, provider: Transcriber
) -> str:
    """Clear our mutable input buffer even on provider failure; never persist it.

    This cannot promise erasure of provider/internal immutable copies. Provider
    retention and network transport must be reviewed before a live adapter ships.
    """
    try:
        return provider.transcribe(bytes(audio), content_type)
    finally:
        audio.clear()


def adapter_status() -> dict:
    return {
        "mode": "mock_transcript",
        "live_capture_available": False,
        "discard_audio_after_transcription": True,
        "speaker_identity_is_authentication": False,
    }
