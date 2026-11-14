"""In-memory operational context pushed by the backend (CV_SPEC.md section 5).

CV stores it and attaches it to events. It never validates business logic.
All pushes are full replaces so repeats are harmless.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime

from pydantic import BaseModel

from cvsvc.events import Attribution


class ActiveTicket(BaseModel):
    ticket_id: str
    set_by: str | None = None
    set_at: str | None = None


class BayAssignment(BaseModel):
    ticket_id: str
    table: str | None = None
    course: str | None = None
    expected_plates: int | None = None


class BaysContext(BaseModel):
    bays: dict[str, BayAssignment | None]


class Claim(BaseModel):
    task_id: str
    server_id: str | None = None


class ClaimsContext(BaseModel):
    claims: dict[str, Claim | None]


def _parse_iso(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class ContextStore:
    def __init__(self, active_ticket_ttl_s: float = 120.0, clock=time.time) -> None:
        self._lock = threading.Lock()
        self.ttl = active_ticket_ttl_s
        self.clock = clock
        self.active_ticket: ActiveTicket | None = None
        self._active_set_local: float | None = None  # local receive time, used if set_at is missing/unparseable
        self._active_version = 0  # increments on every set/clear; used to detect mid-interaction changes
        self.bays: dict[str, BayAssignment | None] = {}
        self.claims: dict[str, Claim | None] = {}

    # ---- writes (from API) ----
    def set_active_ticket(self, t: ActiveTicket) -> None:
        with self._lock:
            same = self.active_ticket is not None and self.active_ticket.model_dump() == t.model_dump()
            if same:
                return  # repeat push after reconnect: no side effects
            self.active_ticket = t
            self._active_set_local = self.clock()
            self._active_version += 1

    def clear_active_ticket(self) -> None:
        with self._lock:
            if self.active_ticket is None:
                return
            self.active_ticket = None
            self._active_set_local = None
            self._active_version += 1

    def set_bays(self, bays: dict[str, BayAssignment | None]) -> None:
        with self._lock:
            self.bays = dict(bays)

    def set_claims(self, claims: dict[str, Claim | None]) -> None:
        with self._lock:
            self.claims = dict(claims)

    # ---- reads ----
    def active_version(self) -> int:
        with self._lock:
            return self._active_version

    def bay(self, bay_id: str) -> BayAssignment | None:
        with self._lock:
            return self.bays.get(bay_id)

    def claim(self, bay_id: str) -> Claim | None:
        with self._lock:
            return self.claims.get(bay_id)

    def attribution(self, version_at_start: int | None = None) -> Attribution:
        """Attribution for an ingredient interaction that started when the
        active-ticket version was `version_at_start`."""
        with self._lock:
            if version_at_start is not None and version_at_start != self._active_version:
                return Attribution(ticket_id=None, method="none", ambiguous=True)
            t = self.active_ticket
            if t is None:
                return Attribution(ticket_id=None, method="none", ambiguous=False)
            set_ts = _parse_iso(t.set_at) or self._active_set_local or 0.0
            if self.clock() - set_ts >= self.ttl:
                return Attribution(ticket_id=None, method="none", ambiguous=False)
            return Attribution(ticket_id=t.ticket_id, method="active_ticket_context", ambiguous=False)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "active_ticket": self.active_ticket.model_dump() if self.active_ticket else None,
                "bays": {k: (v.model_dump() if v else None) for k, v in self.bays.items()},
                "claims": {k: (v.model_dump() if v else None) for k, v in self.claims.items()},
            }
