"""In-memory retry outbox. Enqueue is local only; drain runs off request path.

Restart loses pending receipts/rows. A production transactional outbox must be
committed atomically with operational state; this is a single-process demo seam.
"""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Protocol

from app.analytics.events import CanonicalEvent


class BatchAdapter(Protocol):
    def send(self, events: list[CanonicalEvent]) -> None:
        """Return only on whole-batch success; retry must deduplicate event_id."""


class FakeAdapter:
    """No cloud requests. failures_remaining demonstrates retry health."""

    def __init__(self, failures_remaining: int = 0):
        self.failures_remaining = failures_remaining
        self.events: dict[str, dict] = {}

    def send(self, events: list[CanonicalEvent]) -> None:
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise ConnectionError("Simulated analytics unavailable")
        for event in events:
            existing = self.events.get(event.event_id)
            if existing is not None and existing != event.export():
                raise ValueError("Conflicting event_id at sink")
        for event in events:
            self.events[event.event_id] = event.export()


class JsonlAdapter:
    """Portable local export, not a Databricks connection.

    Existing file rows are checked by event_id. One writer process only; this does
    not provide a cross-process or crash-transactional durable outbox.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def send(self, events: list[CanonicalEvent]) -> None:
        existing = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                event = CanonicalEvent.model_validate_json(line)
                existing[event.event_id] = event.export()
        pending = []
        for event in events:
            row = event.export()
            if event.event_id in existing and existing[event.event_id] != row:
                raise ValueError("Conflicting event_id in JSONL sink")
            if event.event_id not in existing:
                pending.append(row)
                existing[event.event_id] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as output:
            for row in pending:
                output.write(json.dumps(row, sort_keys=True) + "\n")


class SQLWarehouseAdapter(Protocol):
    """Future live adapter: parameterized batch MERGE by event_id.

    No implementation or credential handling is provided here. Workspace edition,
    warehouse availability and official API capabilities need validation first.
    """

    def send(self, events: list[CanonicalEvent]) -> None: ...


class Outbox:
    def __init__(self):
        self._lock = threading.RLock()
        self._drain_lock = threading.Lock()
        self._pending: OrderedDict[str, CanonicalEvent] = OrderedDict()
        self._receipts: dict[str, str] = {}
        self._attempts: dict[str, int] = {}
        self._sent = 0
        self._last_error: str | None = None

    def enqueue(self, events: list[CanonicalEvent]) -> None:
        """Atomic local enqueue; no I/O/network; conflicting identities fail."""
        with self._lock:
            candidates = {}
            for event in events:
                encoded = json.dumps(event.export(), sort_keys=True)
                previous = candidates.get(
                    event.event_id, self._receipts.get(event.event_id)
                )
                if previous is not None and previous != encoded:
                    raise ValueError("event_id reused with changed analytics content")
                candidates[event.event_id] = encoded
            for event in events:
                if event.event_id not in self._receipts:
                    self._receipts[event.event_id] = json.dumps(
                        event.export(), sort_keys=True
                    )
                    self._pending[event.event_id] = event.model_copy(deep=True)
                    self._attempts[event.event_id] = 0

    def drain(self, adapter: BatchAdapter, batch_size: int = 100) -> dict:
        """One nonblocking-to-core batch. Failure retains exact rows for retry."""
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if not self._drain_lock.acquire(blocking=False):
            return self.health()
        try:
            with self._lock:
                batch = list(self._pending.values())[:batch_size]
                for event in batch:
                    self._attempts[event.event_id] += 1
            if not batch:
                return self.health()
            try:
                adapter.send(batch)
            except Exception as exc:
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
            else:
                with self._lock:
                    for event in batch:
                        self._pending.pop(event.event_id, None)
                    self._sent += len(batch)
                    self._last_error = None
            return self.health()
        finally:
            self._drain_lock.release()

    def health(self) -> dict:
        with self._lock:
            return {
                "mode": "in_memory_demo",
                "pending": len(self._pending),
                "sent": self._sent,
                "last_error": self._last_error,
                "pending_attempts": {key: self._attempts[key] for key in self._pending},
                "durable": False,
            }

    def pending(self) -> list[dict]:
        with self._lock:
            return [event.export() for event in self._pending.values()]
