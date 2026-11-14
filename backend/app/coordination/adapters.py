"""Replaceable mock seams. Do not import hardware/paid SDKs into the domain."""

from __future__ import annotations

import re
from typing import Protocol

from app.coordination.contracts import Order, Proposal


class PositioningAdapter(Protocol):
    def suggest(self, actor_id: str) -> dict: ...


class MockPositioning:
    def suggest(self, actor_id: str) -> dict:
        return {
            "mode": "mock",
            "suggested_table_id": "1",
            "requires_manual_review": True,
            "reason": "Deterministic demo fixture, not measured location",
        }


class ReadbackAdapter(Protocol):
    def compare(
        self, order: Order, transcript: str, line_id: str | None, proposal_id: str
    ) -> Proposal: ...


class MockReadback:
    """Constrained grammar: '[seat N] salmon|risotto quantity N'. No freeform NLU."""

    def compare(
        self, order: Order, transcript: str, line_id: str | None, proposal_id: str
    ) -> Proposal:
        text = transcript.lower()
        items = re.findall(r"\b(salmon|risotto)\b", text)
        seat = re.search(r"\bseat\s+(\d+)\b", text)
        qty = re.search(r"\bquantity\s+(\d+)\b", text)
        matches = [
            entry
            for entry in order.lines
            if (not line_id or entry.id == line_id)
            and (not items or entry.menu_id in items)
            and (not seat or entry.seat == int(seat[1]))
        ]
        question = None
        if len(set(items)) != 1 or not qty or not 1 <= int(qty[1]) <= 12:
            question = "Repeat one dish as 'seat 1 salmon quantity 2', or edit the draft directly."
        elif len(matches) != 1:
            question = "Which seat/item should change? Repeated dishes need a seat or line selection; missing dishes can be added manually."
        return Proposal(
            id=proposal_id,
            revision=order.revision,
            transcript=transcript,
            line_id=matches[0].id if len(matches) == 1 else None,
            quantity=int(qty[1]) if qty and not question else None,
            question=question,
        )
