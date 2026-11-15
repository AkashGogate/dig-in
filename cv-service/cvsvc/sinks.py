"""Event sinks: JSONL (always on), WebSocket (always on), stdout, HTTP POST with disk outbox."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)


class JsonlSink:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def send(self, event: dict[str, Any]) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(event) + "\n")


class StdoutSink:
    async def send(self, event: dict[str, Any]) -> None:
        print(json.dumps(event), flush=True)


class WebSocketSink:
    def __init__(self) -> None:
        self.clients: set[Any] = set()

    async def send(self, event: dict[str, Any]) -> None:
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)


class HttpPostSink:
    """POST each event to the backend. Never blocks the camera loop.

    Events go into an in-memory queue drained by a background task. If the
    backend is unreachable, events are appended to the outbox file and the
    outbox is flushed (in order, same event_id) once the backend answers again.
    The deterministic event_id makes retries idempotent on the backend side.
    """

    def __init__(self, url: str, outbox_path: str | Path, max_backoff_s: float = 10.0) -> None:
        self.url = url
        self.outbox = Path(outbox_path)
        self.outbox.parent.mkdir(parents=True, exist_ok=True)
        self.max_backoff_s = max_backoff_s
        self._q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

    async def send(self, event: dict[str, Any]) -> None:
        if self._task is None:
            self._client = httpx.AsyncClient(timeout=3.0)
            self._task = asyncio.create_task(self._run())
        await self._q.put(event)

    def _outbox_events(self) -> list[dict[str, Any]]:
        if not self.outbox.exists():
            return []
        out = []
        for line in self.outbox.read_text().splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    log.warning("skipping corrupt outbox line")
        return out

    def _append_outbox(self, events: list[dict[str, Any]]) -> None:
        with self.outbox.open("a") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")

    async def _post(self, events: list[dict[str, Any]]) -> bool:
        assert self._client is not None
        try:
            r = await self._client.post(self.url, json=events if len(events) > 1 else events[0])
            if r.status_code == 422:
                # malformed per backend: retrying won't help; log and drop
                log.error("backend rejected event(s) as invalid: %s", r.text[:300])
                return True
            return r.status_code < 300
        except httpx.HTTPError:
            return False

    async def _run(self) -> None:
        backoff = 0.5
        while True:
            batch: list[dict[str, Any]] = []
            has_outbox = self.outbox.exists()
            try:
                # with a backlog, wake up periodically to retry the flush
                ev = await asyncio.wait_for(self._q.get(), timeout=backoff if has_outbox else None)
                batch.append(ev)
            except asyncio.TimeoutError:
                pass
            while not self._q.empty():
                batch.append(self._q.get_nowait())
            to_send = self._outbox_events() + batch  # strict order: old outbox first
            if not to_send:
                continue
            if await self._post(to_send):
                self.outbox.unlink(missing_ok=True)
                backoff = 0.5
            else:
                self._append_outbox(batch)
                backoff = min(backoff * 2, self.max_backoff_s)
