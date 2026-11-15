"""Live Deepgram streaming adapter for v2 voice capture (Voice lane).

Off unless DIG_IN_VOICE_LIVE=1 and DEEPGRAM_API_KEY are both set on the server.
Flow: POST /voice/ticket (demo password) -> one-time ticket -> WS /voice/stream.
Audio chunks are forwarded and dropped, never stored. Transcript text goes only
to the capturing browser, which submits it through the normal capture_voice /
kitchen_voice commands; human review and Confirm still gate every order.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlencode

import websockets
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)

from app.demo_auth import auth_required, require_demo_auth
from app.mvp.menu import MenuDocument

log = logging.getLogger("dig_in.voice")

DEEPGRAM_LISTEN = "wss://api.deepgram.com/v1/listen"
GRAMMAR_TERMS = ["table", "heard", "start"]
MAX_KEYTERMS = 100  # Deepgram caps keyterm prompting; keep well under its token limit.
LOW_CONFIDENCE_BELOW = (
    0.6  # calibration knob: flag for review below this Deepgram word-confidence average
)
TICKET_TTL_SECONDS = 30
deepgram_connect = websockets.connect  # swapped in tests


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def live_enabled() -> bool:
    return os.environ.get("DIG_IN_VOICE_LIVE") == "1" and bool(
        os.environ.get("DEEPGRAM_API_KEY")
    )


def keyterms(menu: MenuDocument) -> list[str]:
    seen: dict[str, None] = {}
    for item in menu.items:
        for term in [item.name, *item.aliases, *(m.name for m in item.modifiers)]:
            seen.setdefault(term.strip(), None)
    for term in GRAMMAR_TERMS:
        seen.setdefault(term, None)
    return [t for t in seen if t][:MAX_KEYTERMS]


def listen_url(menu: MenuDocument) -> str:
    params = [
        ("model", "nova-3"),
        ("language", "en"),
        (
            "smart_format",
            "false",
        ),  # live eval: smart_format merged "three, one backhoe" into "31"
        ("punctuate", "true"),
        ("interim_results", "true"),
        ("mip_opt_out", "true"),  # opt out of Deepgram's model-improvement retention
        *(("keyterm", term) for term in keyterms(menu)),
    ]
    return f"{DEEPGRAM_LISTEN}?{urlencode(params)}"


class VoiceLimit(Exception):
    pass


class VoiceBudget:
    """In-memory spend guard.

    ponytail: one-process memory, resets on restart/deploy; the prepaid Deepgram
    balance stays the real ceiling. Move to durable storage if multi-worker.
    """

    def __init__(self) -> None:
        self.max_stream_seconds = _env_float("DIG_IN_VOICE_MAX_STREAM_SECONDS", 30)
        self.daily_audio_seconds = _env_float("DIG_IN_VOICE_DAILY_MINUTES", 30) * 60
        self.streams_per_ip_hour = int(
            _env_float("DIG_IN_VOICE_STREAMS_PER_IP_HOUR", 40)
        )
        self.max_concurrent = int(_env_float("DIG_IN_VOICE_MAX_CONCURRENT", 3))
        # Estimate only; set from your Deepgram plan's streaming rate.
        self.usd_per_minute = _env_float("DIG_IN_DEEPGRAM_USD_PER_MINUTE", 0.0077)
        self.day = datetime.now(UTC).date()
        self.used_seconds = 0.0
        self.streams_started = 0
        self.rejected: dict[str, int] = defaultdict(int)
        self.active: dict[str, int] = defaultdict(int)
        self.starts: dict[str, deque[float]] = defaultdict(deque)

    def _roll_day(self) -> None:
        today = datetime.now(UTC).date()
        if today != self.day:
            self.day, self.used_seconds, self.streams_started = today, 0.0, 0
            self.rejected.clear()

    def remaining_seconds(self) -> float:
        self._roll_day()
        return max(0.0, self.daily_audio_seconds - self.used_seconds)

    def _reject(self, reason: str, message: str):
        self.rejected[reason] += 1
        raise VoiceLimit(message)

    def check(self, ip: str) -> None:
        if self.remaining_seconds() < 1:
            self._reject(
                "daily_budget",
                "Daily live-voice budget used up; use typed text or taps.",
            )
        if sum(self.active.values()) >= self.max_concurrent:
            self._reject(
                "concurrency", "Too many live captures right now; try again shortly."
            )
        if self.active[ip] >= 1:
            self._reject("ip_active", "This device already has a live capture open.")
        starts, now = self.starts[ip], time.monotonic()
        while starts and now - starts[0] > 3600:
            starts.popleft()
        if len(starts) >= self.streams_per_ip_hour:
            self._reject(
                "ip_hourly", "Hourly live-voice limit reached for this device."
            )

    def start(self, ip: str) -> float:
        """Reserve a stream; returns the max seconds this stream may run."""
        self.check(ip)
        self.active[ip] += 1
        self.starts[ip].append(time.monotonic())
        self.streams_started += 1
        return min(self.max_stream_seconds, self.remaining_seconds())

    def finish(self, ip: str, audio_seconds: float) -> None:
        self.active[ip] = max(0, self.active[ip] - 1)
        self._roll_day()
        self.used_seconds += max(0.0, audio_seconds)
        log.info(
            "voice stream closed audio_s=%.1f est_usd=%.4f day_total_s=%.1f",
            audio_seconds,
            audio_seconds / 60 * self.usd_per_minute,
            self.used_seconds,
        )

    def usage(self) -> dict:
        remaining = self.remaining_seconds()
        return {
            "day_utc": self.day.isoformat(),
            "streams_started": self.streams_started,
            "streams_rejected": dict(self.rejected),
            "active_streams": sum(self.active.values()),
            "audio_seconds_used": round(self.used_seconds, 1),
            "audio_seconds_remaining": round(remaining, 1),
            "daily_audio_seconds_limit": self.daily_audio_seconds,
            "max_stream_seconds": self.max_stream_seconds,
            "estimated_usd_used": round(
                self.used_seconds / 60 * self.usd_per_minute, 4
            ),
            "estimated_usd_daily_limit": round(
                self.daily_audio_seconds / 60 * self.usd_per_minute, 4
            ),
            "usd_per_minute_estimate": self.usd_per_minute,
        }


budget = VoiceBudget()
_tickets: dict[str, tuple[str, float]] = {}


def _client_ip(conn: Request | WebSocket) -> str:
    # Behind Fly every connection comes from its proxy; Fly's edge sets
    # Fly-Client-IP. Off Fly the header is spoofable, but global caps still hold.
    return conn.headers.get("fly-client-ip") or (
        conn.client.host if conn.client else "unknown"
    )


def issue_ticket(ip: str) -> str:
    now = time.monotonic()
    for key in [k for k, (_, exp) in _tickets.items() if exp < now]:
        del _tickets[key]
    ticket = secrets.token_urlsafe(24)
    _tickets[ticket] = (ip, now + TICKET_TTL_SECONDS)
    return ticket


def redeem_ticket(ticket: str) -> bool:
    entry = _tickets.pop(ticket, None)
    return entry is not None and entry[1] >= time.monotonic()


async def _send(ws: WebSocket, message: dict) -> None:
    try:
        await ws.send_json(message)
    except Exception:
        pass  # browser left; keep draining Deepgram so usage is still counted


async def relay(ws: WebSocket, menu: MenuDocument, allowed_seconds: float) -> float:
    """Pipe browser audio to Deepgram; return billed audio seconds."""
    started = time.monotonic()
    finals: list[str] = []
    word_confidences: list[float] = []
    billed: float | None = None
    headers = {"Authorization": f"Token {os.environ['DEEPGRAM_API_KEY']}"}
    async with deepgram_connect(listen_url(menu), additional_headers=headers) as dg:

        async def pump() -> None:
            deadline = started + allowed_seconds
            try:
                while True:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        await _send(
                            ws,
                            {
                                "type": "limit",
                                "message": f"Stopped at {allowed_seconds:.0f}s cap.",
                            },
                        )
                        return
                    try:
                        msg = await asyncio.wait_for(ws.receive(), left)
                    except TimeoutError:
                        continue
                    if msg["type"] == "websocket.disconnect":
                        return
                    if msg.get("bytes"):
                        await dg.send(msg["bytes"])  # forwarded, never kept
                    elif (
                        msg.get("text")
                        and json.loads(msg["text"]).get("type") == "stop"
                    ):
                        return
            finally:
                try:
                    await dg.send(json.dumps({"type": "CloseStream"}))
                except Exception:
                    pass

        pump_task = asyncio.create_task(pump())
        try:
            async with asyncio.timeout(allowed_seconds + 15):
                async for raw in dg:
                    event = json.loads(raw)
                    if event.get("type") == "Metadata":
                        billed = float(event.get("duration") or 0)
                    if event.get("type") != "Results":
                        continue
                    alt = event.get("channel", {}).get("alternatives", [{}])[0]
                    text = alt.get("transcript", "")
                    if event.get("is_final"):
                        if text:
                            finals.append(text)
                            word_confidences += [
                                w["confidence"]
                                for w in alt.get("words", [])
                                if "confidence" in w
                            ]
                        await _send(ws, {"type": "final", "text": " ".join(finals)})
                    elif text:
                        await _send(
                            ws, {"type": "interim", "text": " ".join([*finals, text])}
                        )
        finally:
            pump_task.cancel()
    confidence = (
        sum(word_confidences) / len(word_confidences) if word_confidences else None
    )
    await _send(
        ws, {"type": "done", "text": " ".join(finals), "confidence": confidence}
    )
    return billed if billed is not None else time.monotonic() - started


def make_router(get_menu: Callable[[], MenuDocument]) -> APIRouter:
    router = APIRouter(prefix="/voice")

    @router.post("/ticket", dependencies=[Depends(require_demo_auth)])
    def ticket(request: Request):
        if not live_enabled():
            raise HTTPException(
                503, "Live voice is off on this server; use typed text or taps."
            )
        ip = _client_ip(request)
        try:
            budget.check(ip)
        except VoiceLimit as exc:
            raise HTTPException(429, str(exc)) from exc
        return {
            "ticket": issue_ticket(ip),
            "expires_in": TICKET_TTL_SECONDS,
            "max_stream_seconds": min(
                budget.max_stream_seconds, budget.remaining_seconds()
            ),
        }

    @router.get("/usage", dependencies=[Depends(require_demo_auth)])
    def usage():
        return {"live_enabled": live_enabled(), **budget.usage()}

    @router.websocket("/stream")
    async def stream(ws: WebSocket, ticket: str = ""):
        await ws.accept()
        if not live_enabled() or not redeem_ticket(ticket):
            await ws.close(code=4401, reason="Missing, used or expired voice ticket")
            return
        ip = _client_ip(ws)
        try:
            allowed = budget.start(ip)
        except VoiceLimit as exc:
            await _send(ws, {"type": "error", "message": str(exc)})
            await ws.close(code=4429)
            return
        t0 = time.monotonic()
        seconds = 0.0
        try:
            seconds = await relay(ws, get_menu(), allowed)
        except WebSocketDisconnect:
            seconds = time.monotonic() - t0
        except Exception:
            seconds = (
                time.monotonic() - t0
            )  # count wall time so failures can't hide spend
            log.exception("voice relay failed")
            await _send(
                ws,
                {
                    "type": "error",
                    "message": "Live transcription failed; use typed text or taps.",
                },
            )
        finally:
            budget.finish(ip, seconds)
        try:
            await ws.close()
        except Exception:
            pass

    return router


def status() -> dict:
    return {"live_enabled": live_enabled(), "auth_required": auth_required()}
