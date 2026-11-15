"""Backend <-> CV link (BACKEND_SPEC.md section 5).

ContextPusher: the backend is the single writer of CV context. All three pushes
are full replaces, so we simply push the *current* state whenever it changed,
after the DB commit, retrying with backoff. A failed push never rolls back state.
On CV reconnect (boot_id change on /health, or /health coming back after a gap)
everything is pushed again.

Also forwards queued zone resolves (POST /zones/{id}/resolve) and, when
event_source == "ws", subscribes to CV's /events stream as the ingest path.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import httpx

from kbackend.service import Kitchen

log = logging.getLogger(__name__)


class ContextPusher:
    def __init__(self, kitchen: Kitchen, base_url: str, client: httpx.AsyncClient | None = None,
                 health_interval_s: float = 2.0, max_backoff_s: float = 10.0) -> None:
        self.k = kitchen
        self.base = base_url.rstrip("/")
        self.client = client or httpx.AsyncClient(timeout=3.0)
        self.health_interval_s = health_interval_s
        self.max_backoff_s = max_backoff_s
        self.pushed_version = -1
        self.cv_boot_id: str | None = None
        self.cv_up = False
        self._wake = asyncio.Event()
        self.last_error: str | None = None

    def poke(self) -> None:
        self._wake.set()

    async def push_all(self) -> bool:
        version = self.k.context_version
        bays, claims, active = self.k.bays_context(), self.k.claims_context(), self.k.active_ticket_context()
        try:
            r1 = await self.client.put(f"{self.base}/context/bays", json=bays)
            r2 = await self.client.put(f"{self.base}/context/claims", json=claims)
            if active:
                r3 = await self.client.put(f"{self.base}/context/active_ticket", json=active)
            else:
                r3 = await self.client.delete(f"{self.base}/context/active_ticket")
            ok = all(r.status_code < 300 for r in (r1, r2, r3))
        except httpx.HTTPError as e:
            self.last_error = repr(e)
            return False
        if ok:
            self.pushed_version = version
            self.last_error = None
        else:
            self.last_error = f"CV answered {r1.status_code}/{r2.status_code}/{r3.status_code}"
        return ok

    async def flush_cv_calls(self) -> bool:
        while self.k.cv_calls:
            call = self.k.cv_calls[0]
            try:
                r = await self.client.post(f"{self.base}/zones/{call['zone_id']}/resolve",
                                           json={"count": call["count"]})
            except httpx.HTTPError as e:
                self.last_error = repr(e)
                return False
            if r.status_code >= 500 or r.status_code == 503:
                return False
            if r.status_code >= 300:
                log.warning("CV refused zone resolve %s: %s", call, r.text[:200])
            # drop the call we just sent (unless a newer one for the zone replaced it meanwhile)
            if self.k.cv_calls and self.k.cv_calls[0] is call:
                self.k.cv_calls.pop(0)
        return True

    async def check_health(self) -> None:
        try:
            r = await self.client.get(f"{self.base}/health")
            boot = r.json().get("boot_id") if r.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            if self.cv_up:
                log.warning("CV service unreachable")
            self.cv_up = False
            return
        reconnected = not self.cv_up or (boot is not None and boot != self.cv_boot_id)
        self.cv_up, self.cv_boot_id = True, boot
        if reconnected:
            log.info("CV (re)connected (boot %s): re-pushing all context", boot)
            self.pushed_version = -1

    async def run(self) -> None:
        backoff = 0.5
        last_health = 0.0
        loop = asyncio.get_running_loop()
        while True:
            if loop.time() - last_health >= self.health_interval_s:
                last_health = loop.time()
                await self.check_health()
            ok = True
            if self.pushed_version != self.k.context_version:
                ok = await self.push_all()
            if ok and self.k.cv_calls:
                ok = await self.flush_cv_calls()
            if ok:
                backoff = 0.5
                timeout = self.health_interval_s
            else:
                timeout = backoff
                backoff = min(backoff * 2, self.max_backoff_s)
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass


async def subscribe_cv_events(ws_url: str, on_events: Callable[[list[dict[str, Any]]], Awaitable[None]]) -> None:
    """event_source=ws: consume CV's /events WebSocket as the ingest path."""
    import websockets  # provided by uvicorn[standard]

    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                log.info("subscribed to CV events at %s", ws_url)
                async for msg in ws:
                    try:
                        ev = json.loads(msg)
                    except json.JSONDecodeError:
                        continue
                    await on_events([ev])
        except Exception as e:  # reconnect forever
            log.warning("CV event stream dropped (%r); retrying", e)
            await asyncio.sleep(2)
