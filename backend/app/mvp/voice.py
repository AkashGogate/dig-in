"""Constrained menu-driven voice parsing. Inputs are ephemeral, never logged.

No transcription provider, noisy-room guarantee or speaker authentication is
implemented here. A provider adapter can return text to these same functions.
"""

from __future__ import annotations

import math
import re
from collections import Counter
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


def _number(token: str) -> str:
    """Live STT often spells small numbers ('table four'); normalize to digits."""
    return str(NUMBER_WORDS.get(token.lower(), token))


SIMILARITY_MIN = 0.5  # calibration knob: retune on real misheard kitchen transcripts


def _vector(text: str) -> Counter:
    joined = f" {normalize(text).replace(' ', '')} "  # robust to 'bull dozer' splits
    return Counter(joined[i : i + 3] for i in range(len(joined) - 2))


def _cosine(a: Counter, b: Counter) -> float:
    dot = sum(a[k] * b[k] for k in a.keys() & b.keys())
    norm = math.sqrt(sum(v * v for v in a.values()) * sum(v * v for v in b.values()))
    return dot / norm if norm else 0.0


def suggest_items(menu: MenuDocument, text: str, limit: int = 3) -> list[str]:
    """Secondary, deterministic layer: rank likely misheard dish names.

    Character-trigram vectors + cosine similarity over 1-3 word spans of the
    phrase. Returns review candidates only; exact alias matching stays the
    authority and nothing here ever selects an item.
    """
    words = normalize(text).split()
    spans = [
        _vector(" ".join(words[i : i + n]))
        for n in (1, 2, 3)
        for i in range(len(words) - n + 1)
    ]
    scores = {
        item.id: max(
            (_cosine(span, _vector(alias)) for span in spans for alias in names(item)),
            default=0.0,
        )
        for item in menu.items
    }
    ranked = sorted(
        (-score, item_id)
        for item_id, score in scores.items()
        if score >= SIMILARITY_MIN
    )
    return [item_id for _, item_id in ranked[:limit]]


def _with_suggestions(menu: MenuDocument, phrase: str, flags: list[dict]) -> list[dict]:
    return [
        {**flag, "candidates": suggest_items(menu, phrase)}
        if flag["code"] == "unknown_item" and not flag.get("candidates")
        else flag
        for flag in flags
    ]


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


def parse_order(menu: MenuDocument, text: str, selected_table_id: str) -> dict:
    table = re.match(r"^\s*table\s+(" + NUMBER + r")\b[\s:,.]*", text, re.IGNORECASE)
    spoken_table = _number(table[1]) if table else None
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
        phrase = clause[number.end() :] if number else clause
        matched = match_menu(menu, phrase)
        flags.extend(
            {**flag, "line_index": index}
            for flag in _with_suggestions(menu, phrase, matched["flags"])
        )
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
    heard = re.fullmatch(r"heard table (" + NUMBER + r")", clean)
    if heard:
        return {
            "action": "acknowledge",
            "table_id": _number(heard[1]),
            "menu_id": None,
            "flags": [],
        }
    started = re.fullmatch(r"start table (" + NUMBER + r") (.+)", clean)
    if started:
        matched = match_menu(menu, started[2])
        return {
            "action": "start_dish"
            if matched["status"] == "matched" and not matched["modifiers"]
            else None,
            "table_id": _number(started[1]),
            "menu_id": matched["menu_id"],
            "flags": _with_suggestions(menu, started[2], matched["flags"])
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
    from app.mvp.voice_live import status

    live = status()
    return {
        "mode": "deepgram_stream" if live["live_enabled"] else "mock_transcript",
        "live_capture_available": live["live_enabled"],
        "auth_required": live["auth_required"],
        "discard_audio_after_transcription": True,
        "speaker_identity_is_authentication": False,
    }
