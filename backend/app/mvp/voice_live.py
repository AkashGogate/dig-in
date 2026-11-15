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
import math
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from urllib.parse import urlencode

import websockets
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, ConfigDict, Field

from app.demo_auth import auth_required, require_demo_auth
from app.mvp.menu import MenuDocument

log = logging.getLogger("dig_in.voice")

DEEPGRAM_LISTEN = "wss://api.deepgram.com/v1/listen"
GRAMMAR_TERMS = ["table", "heard", "start"]
MAX_KEYTERMS = 100  # Deepgram caps keyterm prompting; keep well under its token limit.
LOW_CONFIDENCE_BELOW = 0.6  # Provisional review threshold, not calibrated accuracy.
TICKET_TTL_SECONDS = 30
deepgram_connect = websockets.connect  # swapped in tests


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def live_enabled() -> bool:
    return os.environ.get("DIG_IN_VOICE_LIVE") == "1" and bool(
        os.environ.get("DEEPGRAM_API_KEY")
    )


def keyterms(menu: MenuDocument) -> list[str]:
    seen: dict[str, None] = dict.fromkeys(GRAMMAR_TERMS)
    for item in menu.items:
        for term in [item.name, *item.aliases, *(m.name for m in item.modifiers)]:
            seen.setdefault(term.strip(), None)
    for term in GRAMMAR_TERMS:
        seen.setdefault(term, None)
    # Conservative UTF-8 byte budget, including per-term boundary headroom.
    # Do not let a mutable 500-item menu create an unbounded keyterm request.
    terms, size = [], 0
    for term in seen:
        cost = len(term.encode("utf-8")) + 2
        if term and size + cost <= 400 and len(terms) < MAX_KEYTERMS:
            terms.append(term)
            size += cost
    return terms


def listen_url(menu: MenuDocument) -> str:
    params = [
        ("model", "nova-3"),
        ("encoding", "linear16"),
        ("sample_rate", "16000"),
        ("channels", "1"),
        ("language", "en"),
        ("smart_format", "false"),  # Avoid merging table and quantity into one number.
        ("punctuate", "true"),
        ("interim_results", "true"),
        ("mip_opt_out", "true"),
        ("redact_usage", "true"),  # redact keyterm text in provider usage metadata
        *(("keyterm", term) for term in keyterms(menu)),
    ]
    return f"{DEEPGRAM_LISTEN}?{urlencode(params)}"


class VoiceLimit(Exception):
    pass


def synchronized(fn):
    @wraps(fn)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return fn(self, *args, **kwargs)

    return wrapped


class VoiceBudget:
    """In-memory spend guard.

    ponytail: one-process memory, resets on restart/deploy; the prepaid Deepgram
    balance stays the real ceiling. Move to durable storage if multi-worker.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.reserved: dict[str, float] = {}
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

    @synchronized
    def remaining_seconds(self) -> float:
        self._roll_day()
        return max(
            0.0,
            self.daily_audio_seconds - self.used_seconds - sum(self.reserved.values()),
        )

    def _reject(self, reason: str, message: str):
        self.rejected[reason] += 1
        raise VoiceLimit(message)

    @synchronized
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

    @synchronized
    def start(self, ip: str) -> float:
        """Reserve a stream; returns the max seconds this stream may run."""
        self.check(ip)
        allowance = min(self.max_stream_seconds, self.remaining_seconds())
        self.reserved[ip] = allowance
        self.active[ip] += 1
        self.starts[ip].append(time.monotonic())
        self.streams_started += 1
        return allowance

    @synchronized
    def finish(self, ip: str, audio_seconds: float) -> None:
        self.reserved.pop(ip, None)
        self.active[ip] = max(0, self.active[ip] - 1)
        self._roll_day()
        self.used_seconds += max(0.0, audio_seconds)
        log.info(
            "voice stream closed audio_s=%.1f est_usd=%.4f day_total_s=%.1f",
            audio_seconds,
            audio_seconds / 60 * self.usd_per_minute,
            self.used_seconds,
        )

    @synchronized
    def usage(self) -> dict:
        remaining = self.remaining_seconds()
        return {
            "day_utc": self.day.isoformat(),
            "streams_started": self.streams_started,
            "streams_rejected": dict(self.rejected),
            "active_streams": sum(self.active.values()),
            "audio_seconds_used": round(self.used_seconds, 1),
            "audio_seconds_remaining": round(remaining, 1),
            "audio_seconds_reserved": round(sum(self.reserved.values()), 1),
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
_tickets: dict[str, tuple[str, float, MenuDocument, str]] = {}


class VoiceTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: str | None = Field(default=None, max_length=120)
    menu_revision: str | None = Field(default=None, max_length=100)


def _client_ip(conn: Request | WebSocket) -> str:
    # Rate metadata only. The credentialed HTTP proxy and direct WebSocket can
    # have different IPs; bearer tickets bind the demo session, never an IP.
    return conn.headers.get("fly-client-ip") or (
        conn.client.host if conn.client else "unknown"
    )


def issue_ticket(ip: str, menu: MenuDocument, session_id: str) -> str:
    now = time.monotonic()
    for key in [k for k, (_, exp, _, _) in _tickets.items() if exp < now]:
        del _tickets[key]
    ticket = secrets.token_urlsafe(24)
    _tickets[ticket] = (
        ip,
        now + TICKET_TTL_SECONDS,
        menu.model_copy(deep=True),
        session_id,
    )
    return ticket


def redeem_ticket(ticket: str, session_id: str) -> tuple[MenuDocument, str] | None:
    entry = _tickets.get(ticket)
    if entry is None or entry[1] < time.monotonic():
        _tickets.pop(ticket, None)
        return None
    if not session_id or entry[3] != session_id:
        return None
    _tickets.pop(ticket, None)
    return entry[2], entry[0]


async def _send(ws: WebSocket, message: dict) -> None:
    try:
        await ws.send_json(message)
    except Exception:
        pass  # browser left; keep draining Deepgram so usage is still counted


def transcript_confidence(alternative: dict) -> float | None:
    """Conservative final-word confidence; missing metadata is unknown, not high.

    Shared by live relay and prerecorded evaluator. This is a review hint, not
    authenticated provider proof or a calibrated probability of correctness.
    """
    words = alternative.get("words")
    if not isinstance(words, list) or not words:
        return None
    values = []
    for word in words:
        value = word.get("confidence") if isinstance(word, dict) else None
        if not (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and 0 <= value <= 1
        ):
            return None
        values.append(float(value))
    return min(values)


async def relay(ws: WebSocket, menu: MenuDocument, allowed_seconds: float) -> float:
    """Pipe browser audio to Deepgram; return billed audio seconds."""
    started = time.monotonic()
    finals: list[str] = []
    word_confidences: list[float | None] = []
    billed: float | None = None
    accepted_bytes = 0
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
                        chunk = msg["bytes"]
                        # Declared mono PCM16 at 16kHz: sample count is duration.
                        # Refuse accelerated audio as well as oversized messages.
                        nonlocal accepted_bytes
                        proposed = accepted_bytes + len(chunk)
                        elapsed = time.monotonic() - started
                        if (
                            len(chunk) % 2
                            or len(chunk) > 64000
                            or proposed > int(allowed_seconds * 32000)
                            or proposed > int((elapsed + 1.0) * 32000)
                        ):
                            await _send(
                                ws,
                                {
                                    "type": "error",
                                    "message": "Audio format/rate limit exceeded; use mono PCM16 at 16kHz in real time.",
                                },
                            )
                            return
                        accepted_bytes = proposed
                        await dg.send(chunk)  # forwarded, never retained
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
                    alternatives = event.get("channel", {}).get("alternatives") or [{}]
                    alt = alternatives[0]
                    text = alt.get("transcript", "")
                    if event.get("is_final"):
                        if text:
                            finals.append(text)
                            word_confidences.append(transcript_confidence(alt))
                        await _send(ws, {"type": "final", "text": " ".join(finals)})
                    elif text:
                        await _send(
                            ws, {"type": "interim", "text": " ".join([*finals, text])}
                        )
        finally:
            pump_task.cancel()
    confidence = (
        min(word_confidences)
        if word_confidences and all(v is not None for v in word_confidences)
        else None
    )
    await _send(
        ws, {"type": "done", "text": " ".join(finals), "confidence": confidence}
    )
    return billed if billed is not None else accepted_bytes / 32000


def make_router(
    get_menu: Callable[[], MenuDocument], get_pinned_menu: Callable | None = None
) -> APIRouter:
    router = APIRouter(prefix="/voice")

    @router.post("/ticket", dependencies=[Depends(require_demo_auth)])
    def ticket(
        request: Request,
        body: VoiceTicketRequest | None = None,
        x_demo_session: str = Header(default=""),
    ):
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
            "ticket": issue_ticket(
                ip,
                get_pinned_menu(body, x_demo_session)
                if get_pinned_menu is not None
                else get_menu(),
                x_demo_session,
            ),
            "encoding": "linear16",
            "sample_rate": 16000,
            "channels": 1,
            "expires_in": TICKET_TTL_SECONDS,
            "max_stream_seconds": min(
                budget.max_stream_seconds, budget.remaining_seconds()
            ),
        }

    @router.get("/usage", dependencies=[Depends(require_demo_auth)])
    def usage():
        return {"live_enabled": live_enabled(), **budget.usage()}

    @router.websocket("/stream")
    async def stream(ws: WebSocket, ticket: str = "", session_id: str = ""):
        await ws.accept()
        redeemed = redeem_ticket(ticket, session_id)
        if not live_enabled() or redeemed is None:
            await ws.close(code=4401, reason="Missing, used or expired voice ticket")
            return
        pinned_menu, ip = redeemed
        try:
            allowed = budget.start(ip)
        except VoiceLimit as exc:
            await _send(ws, {"type": "error", "message": str(exc)})
            await ws.close(code=4429)
            return
        seconds = 0.0
        try:
            seconds = await relay(ws, pinned_menu, allowed)
        except WebSocketDisconnect:
            seconds = allowed
        except Exception:
            seconds = allowed  # conservative charge on unknown provider failure
            log.warning("voice relay failed; reserved allowance charged")
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
    return {
        "live_enabled": live_enabled(),
        "auth_required": auth_required(),
        "audio_format": "mono_pcm16_16000",
        "requires_audio_context": True,
    }
