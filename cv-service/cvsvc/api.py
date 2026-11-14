"""FastAPI app (CV_SPEC.md section 8)."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from cvsvc.config import CVConfig
from cvsvc.context import ActiveTicket, BaysContext, ClaimsContext, ContextStore
from cvsvc.events import EventBus
from cvsvc.sinks import WebSocketSink


class StateView:
    """Latest observed state, folded from the event stream (works for mock and real cameras)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.zones: dict[str, dict[str, Any]] = {}
        self.bays: dict[str, dict[str, Any]] = {}
        self.cameras: dict[str, dict[str, Any]] = {}

    def __call__(self, ev: dict[str, Any]) -> None:
        t, p = ev["type"], ev["payload"]
        with self._lock:
            if t == "ZONE_SNAPSHOT":
                self.zones[ev["zone_id"]] = {"ingredient": p["ingredient"], "count": p["count"], "at": ev["observed_at"]}
            elif t in ("INGREDIENT_PICKED", "INGREDIENT_RETURNED"):
                self.zones[ev["zone_id"]] = {"ingredient": p["ingredient"], "count": p["count_after"], "at": ev["observed_at"]}
            elif t == "INGREDIENT_CHANGE_PENDING":
                z = self.zones.setdefault(ev["zone_id"], {"ingredient": p["ingredient"], "count": p["count_before"]})
                z["pending"] = {"reason": p["reason"], "estimate": p["count_after_estimate"], "at": ev["observed_at"]}
            elif t == "BAY_STATE":
                self.bays[ev["bay_id"]] = {**p, "at": ev["observed_at"]}
            elif t in ("PLATE_ARRIVED", "PLATE_REMOVED"):
                b = self.bays.setdefault(ev["bay_id"], {})
                b.update(plate_count=p["count_after"], occupied=p["count_after"] > 0, at=ev["observed_at"])
            elif t == "CAMERA_STATUS":
                self.cameras[ev["camera_id"]] = {"state": p["state"], "reason": p["reason"], "since": p["since"],
                                                 "last_heartbeat_at": ev["observed_at"]}

    def clear_pending(self, zone_id: str) -> None:
        with self._lock:
            if zone_id in self.zones:
                self.zones[zone_id].pop("pending", None)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"zones": dict(self.zones), "bays": dict(self.bays), "cameras": dict(self.cameras)}


class ResolveBody(BaseModel):
    count: int


class PlateMove(BaseModel):
    delta: int


class CameraStateBody(BaseModel):
    state: str
    reason: str | None = None


@dataclass
class Runtime:
    cfg: CVConfig
    bus: EventBus
    context: ContextStore
    ws_sink: WebSocketSink
    state: StateView
    mode: str = "camera"  # "camera" | "mock"
    resolve_zone: Callable[[str, int], Awaitable[None]] | None = None
    capture_reference: Callable[[str], Awaitable[str]] | None = None
    mjpeg: Callable[[str], Any] | None = None  # returns an iterator of JPEG bytes for a camera
    health: Callable[[], dict[str, Any]] | None = None
    mock: Any = None
    background: list[Callable[[], Awaitable[None]]] = field(default_factory=list)


def create_app(rt: Runtime) -> FastAPI:
    tasks: list[asyncio.Task] = []

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await rt.bus.start()
        for job in rt.background:
            tasks.append(asyncio.create_task(job()))
        yield
        for t in tasks:
            t.cancel()

    app = FastAPI(title="dig-in cv-service", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.state.rt = rt

    @app.get("/health")
    async def health():
        cams = rt.health() if rt.health else rt.state.snapshot()["cameras"]
        return {"status": "ok", "mode": rt.mode, "boot_id": rt.bus.ids.boot_id, "cameras": cams}

    @app.get("/state")
    async def state():
        return {"mode": rt.mode, **rt.state.snapshot(), "context": rt.context.snapshot()}

    @app.websocket("/events")
    async def events_ws(ws: WebSocket):
        await ws.accept()
        rt.ws_sink.clients.add(ws)
        try:
            while True:
                await ws.receive_text()  # keepalive; client messages are ignored
        except WebSocketDisconnect:
            pass
        finally:
            rt.ws_sink.clients.discard(ws)

    @app.get("/events/recent")
    async def recent(n: int = Query(100, ge=1, le=500)):
        return list(rt.bus.recent)[-n:]

    # ---- context (only the backend calls these) ----
    @app.put("/context/active_ticket")
    async def put_active(body: ActiveTicket):
        rt.context.set_active_ticket(body)
        return {"ok": True, "context": rt.context.snapshot()}

    @app.delete("/context/active_ticket")
    async def del_active():
        rt.context.clear_active_ticket()
        return {"ok": True}

    @app.put("/context/bays")
    async def put_bays(body: BaysContext):
        rt.context.set_bays(body.bays)
        return {"ok": True}

    @app.put("/context/claims")
    async def put_claims(body: ClaimsContext):
        rt.context.set_claims(body.claims)
        return {"ok": True}

    # ---- zones / calibration / debug ----
    @app.post("/zones/{zone_id}/resolve")
    async def resolve(zone_id: str, body: ResolveBody):
        if rt.resolve_zone is None:
            raise HTTPException(503, "ingredient tracking not running")
        try:
            await rt.resolve_zone(zone_id, body.count)
        except KeyError:
            raise HTTPException(404, f"unknown zone {zone_id}")
        rt.state.clear_pending(zone_id)
        return {"ok": True, "zone_id": zone_id, "count": body.count}

    @app.post("/calibrate/{camera_id}/reference")
    async def calibrate(camera_id: str):
        if rt.capture_reference is None:
            raise HTTPException(503, "no live camera in this mode")
        try:
            path = await rt.capture_reference(camera_id)
        except KeyError:
            raise HTTPException(404, f"unknown camera {camera_id}")
        return {"ok": True, "path": path}

    @app.get("/debug/{camera_id}.mjpg")
    async def debug_stream(camera_id: str):
        if rt.mjpeg is None:
            raise HTTPException(503, "no live camera in this mode")
        try:
            gen = rt.mjpeg(camera_id)
        except KeyError:
            raise HTTPException(404, f"unknown camera {camera_id}")
        return StreamingResponse(gen, media_type="multipart/x-mixed-replace; boundary=frame")

    # ---- mock controls ----
    if rt.mock is not None:
        @app.post("/mock/bays/{bay_id}/plates")
        async def mock_plates(bay_id: str, body: PlateMove):
            if bay_id not in rt.mock.bays:
                raise HTTPException(404, f"unknown bay {bay_id}")
            await rt.mock.move_plates(bay_id, body.delta)
            return {"ok": True, "count": rt.mock.bays[bay_id].count}

        @app.post("/mock/cameras/{camera_id}")
        async def mock_camera(camera_id: str, body: CameraStateBody):
            if camera_id not in rt.mock.camera_state:
                raise HTTPException(404, f"unknown camera {camera_id}")
            await rt.mock.set_camera_state(camera_id, body.state, body.reason)
            return {"ok": True}

    return app
