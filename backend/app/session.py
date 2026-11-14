"""Public-demo abuse/cost controls (ARCHITECTURE.md #2.1 / #6).

A session wraps one live-mic or test-scenario run: it enforces a hard
wall-clock cap and gives the server a single kill switch per session.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

MAX_SESSION_SECONDS = 120
MAX_CONCURRENT_SESSIONS_PER_IP = 2

# Bot/abuse backstops: a single misbehaving IP is capped by rate, and the whole
# app is capped by a global daily ceiling so distributed bot traffic across many
# IPs still can't run the Deepgram balance to zero (ARCHITECTURE.md #6).
MAX_SESSIONS_PER_IP_PER_HOUR = 10
MAX_GLOBAL_SESSIONS_PER_DAY = 200

# ponytail: in-process state, fine for one demo instance; swap for Redis if this ever runs multi-process.
_sessions_per_ip: dict[str, int] = defaultdict(int)
_session_starts_per_ip: dict[str, deque[float]] = defaultdict(deque)
_global_session_starts: deque[float] = deque()


class SessionLimitExceeded(Exception):
    pass


def _prune_older_than(times: deque[float], now: float, window_seconds: float) -> None:
    while times and now - times[0] > window_seconds:
        times.popleft()


class KitchenSession:
    def __init__(self, session_id: str, client_ip: str) -> None:
        now = time.monotonic()

        _prune_older_than(_global_session_starts, now, 86400)
        if len(_global_session_starts) >= MAX_GLOBAL_SESSIONS_PER_DAY:
            raise SessionLimitExceeded("demo session limit reached for today; try again later")

        ip_starts = _session_starts_per_ip[client_ip]
        _prune_older_than(ip_starts, now, 3600)
        if len(ip_starts) >= MAX_SESSIONS_PER_IP_PER_HOUR:
            raise SessionLimitExceeded(f"{client_ip} exceeded {MAX_SESSIONS_PER_IP_PER_HOUR} sessions/hour")

        if _sessions_per_ip[client_ip] >= MAX_CONCURRENT_SESSIONS_PER_IP:
            raise SessionLimitExceeded(f"{client_ip} already has {MAX_CONCURRENT_SESSIONS_PER_IP} active sessions")

        self.session_id = session_id
        self.client_ip = client_ip
        self._started_at = now
        self._killed = False
        _sessions_per_ip[client_ip] += 1
        ip_starts.append(now)
        _global_session_starts.append(now)

    def seconds_remaining(self) -> float:
        return max(0.0, MAX_SESSION_SECONDS - (time.monotonic() - self._started_at))

    def expired(self) -> bool:
        return self._killed or self.seconds_remaining() <= 0

    def kill(self) -> None:
        """Single entry point to tear down a session — ARCHITECTURE.md's 'easy kill switch'."""
        self._killed = True

    def close(self) -> None:
        if not self._killed:
            self._killed = True
        if _sessions_per_ip[self.client_ip] > 0:
            _sessions_per_ip[self.client_ip] -= 1

    async def watchdog(self) -> None:
        """Await this alongside the pipeline task; returns when the session should stop."""
        while not self.expired():
            await asyncio.sleep(1)
