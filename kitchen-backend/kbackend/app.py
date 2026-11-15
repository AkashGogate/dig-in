"""FastAPI app: CV ingest + endpoints for the UI and voice teammates (BACKEND_SPEC.md section 10)."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from kbackend.config import Settings, load_settings
from kbackend.cvlink import ContextPusher, subscribe_cv_events
from kbackend.db import connect
from kbackend.service import Conflict, Invalid, Kitchen, NotFound

log = logging.getLogger(__name__)


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def broadcast(self, msgs: list[dict[str, Any]]) -> None:
        if not msgs:
            return
        dead = []
        for ws in list(self.clients):
            try:
                for m in msgs:
                    await ws.send_json(m)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)


# ---- request bodies ----
class TicketIn(BaseModel):
    table: str | None = None
    course: str | None = None
    plates_expected: int = 1
    dishes: list[str] = []
    seats: list[Any] | None = None
    vip: bool = False
    id: str | None = None


class StatusIn(BaseModel):
    status: str


class ActorIn(BaseModel):
    server_id: str | None = None
    source: str | None = None  # e.g. "cook_voice", "kitchen_ui"; stored in the log


class ClaimIn(BaseModel):
    server_id: str


class BlockIn(BaseModel):
    reason: str | None = None


class ActiveTicketIn(BaseModel):
    ticket_id: str
    set_by: str | None = None


class ResolveIn(BaseModel):
    resolution: str
    count: int | None = None
    staff_id: str | None = None
    ticket_id: str | None = None


class QtyIn(BaseModel):
    qty: int
    staff_id: str | None = None


class CountIn(BaseModel):
    count: int
    staff_id: str | None = None


class OverrideIn(BaseModel):
    action: str  # clear | reassign
    ticket_id: str | None = None
    staff_id: str | None = None
    confirm: bool = False


def create_app(settings: Settings | None = None, kitchen: Kitchen | None = None,
               pusher: ContextPusher | None = None) -> FastAPI:
    settings = settings or load_settings(os.environ.get("KITCHEN_CONFIG", "config.yaml"))
    k = kitchen or Kitchen(settings, connect(settings.db_path))
    hub = Hub()
    if pusher is None and settings.push_context:
        pusher = ContextPusher(k, settings.cv_base_url)

    async def after_change() -> None:
        """Fan out to the UI and nudge the CV context pusher (after commit)."""
        await hub.broadcast(k.changes())
        if pusher is not None:
            pusher.poke()

    async def ingest(events: list[dict[str, Any]]) -> dict[str, Any]:
        result = await asyncio.to_thread(k.ingest, events)
        await after_change()
        return result

    async def stale_loop() -> None:
        while True:
            await asyncio.sleep(1.0)
            try:
                if await asyncio.to_thread(k.check_stale):
                    await after_change()
            except Exception:
                log.exception("stale check failed")

    tasks: list[asyncio.Task] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tasks.append(asyncio.create_task(stale_loop()))
        if pusher is not None:
            tasks.append(asyncio.create_task(pusher.run()))
        if settings.event_source == "ws":
            ws_url = settings.cv_base_url.replace("http", "ws", 1).rstrip("/") + "/events"
            tasks.append(asyncio.create_task(subscribe_cv_events(ws_url, lambda evs: ingest(evs))))
        yield
        for t in tasks:
            t.cancel()

    app = FastAPI(title="dig-in kitchen backend", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.state.kitchen = k
    app.state.pusher = pusher

    @app.exception_handler(NotFound)
    async def _nf(_: Request, e: NotFound):
        return JSONResponse({"detail": str(e)}, status_code=404)

    @app.exception_handler(Conflict)
    async def _cf(_: Request, e: Conflict):
        return JSONResponse({"detail": str(e), **e.detail}, status_code=409)

    @app.exception_handler(Invalid)
    async def _iv(_: Request, e: Invalid):
        return JSONResponse({"detail": str(e)}, status_code=400)

    async def run(fn, *args, **kwargs):
        out = await asyncio.to_thread(fn, *args, **kwargs)
        await after_change()
        return out

    # ---- CV ingest ----
    @app.post("/cv/events")
    async def cv_events(body: Any = Body(...)):
        events = body if isinstance(body, list) else [body]
        if not all(isinstance(e, dict) for e in events):
            raise HTTPException(422, "expected an event object or an array of events")
        result = await ingest(events)
        if result["rejected"] and not result["accepted"] and not result["duplicates"]:
            return JSONResponse(result, status_code=422)
        return result

    # ---- live + snapshot ----
    @app.websocket("/ws")
    async def ws(ws: WebSocket):
        await ws.accept()
        await ws.send_json({"kind": "state", "data": await asyncio.to_thread(k.state)})
        hub.clients.add(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            hub.clients.discard(ws)

    @app.get("/state")
    async def state():
        s = await asyncio.to_thread(k.state)
        if pusher is not None:
            s["cv_link"] = {"up": pusher.cv_up, "boot_id": pusher.cv_boot_id,
                            "context_in_sync": pusher.pushed_version == k.context_version,
                            "last_error": pusher.last_error}
        return s

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # ---- tickets ----
    @app.post("/tickets", status_code=201)
    async def create_ticket(body: TicketIn):
        return await run(k.create_ticket, body.table, body.course, body.plates_expected, body.dishes,
                         body.seats, body.vip, body.id)

    @app.get("/tickets/{ticket_id}")
    async def get_ticket(ticket_id: str):
        t = await asyncio.to_thread(k.ticket, ticket_id)
        if t is None:
            raise HTTPException(404, "ticket not found")
        return t

    @app.post("/tickets/{ticket_id}/status")
    async def ticket_status(ticket_id: str, body: StatusIn):
        return await run(k.advance_ticket, ticket_id, body.status)

    @app.post("/tickets/{ticket_id}/cooking-complete")
    async def cooking_complete(ticket_id: str):
        return await run(k.cooking_complete, ticket_id)

    @app.post("/tickets/{ticket_id}/ready")
    async def ready(ticket_id: str, body: ActorIn | None = None):
        return await run(k.declare_ready, ticket_id)

    @app.post("/tickets/{ticket_id}/served")
    async def served(ticket_id: str, body: ActorIn | None = None):
        return await run(k.confirm_served, ticket_id, body.server_id if body else None)

    @app.post("/tickets/{ticket_id}/cancel")
    async def cancel(ticket_id: str):
        return await run(k.cancel_ticket, ticket_id)

    # ---- tasks ----
    @app.get("/tasks")
    async def tasks_list():
        return await asyncio.to_thread(k.task_queue)

    @app.post("/tasks/{task_id}/claim")
    async def claim(task_id: str, body: ClaimIn):
        return await run(k.claim_task, task_id, body.server_id)

    @app.post("/tasks/{task_id}/release")
    async def release(task_id: str, body: ActorIn | None = None):
        return await run(k.release_task, task_id, body.server_id if body else None)

    @app.post("/tasks/{task_id}/complete")
    async def complete(task_id: str, body: ActorIn | None = None):
        return await run(k.complete_task, task_id, body.server_id if body else None)

    @app.post("/tasks/{task_id}/block")
    async def block(task_id: str, body: BlockIn | None = None):
        return await run(k.block_task, task_id, body.reason if body else None)

    # ---- active ticket ----
    @app.put("/active-ticket")
    async def put_active(body: ActiveTicketIn):
        return await run(k.set_active_ticket, body.ticket_id, body.set_by)

    @app.delete("/active-ticket")
    async def del_active():
        await run(k.clear_active_ticket)
        return {"ok": True}

    # ---- review queue ----
    @app.get("/review-items")
    async def review_items(status: str = "open"):
        return await asyncio.to_thread(k.review_items, status)

    @app.post("/review-items/{item_id}/resolve")
    async def resolve(item_id: int, body: ResolveIn):
        return await run(k.resolve_review, item_id, body.resolution, body.count, body.staff_id, body.ticket_id)

    # ---- inventory ----
    @app.post("/inventory/{zone_id}/restock")
    async def restock(zone_id: str, body: QtyIn):
        return await run(k.restock, zone_id, body.qty, body.staff_id)

    @app.post("/inventory/{zone_id}/waste")
    async def waste(zone_id: str, body: QtyIn):
        return await run(k.waste, zone_id, body.qty, body.staff_id)

    @app.post("/inventory/{zone_id}/correct")
    async def correct(zone_id: str, body: CountIn):
        return await run(k.correct, zone_id, body.count, body.staff_id)

    # ---- bays ----
    @app.post("/bays/{bay_id}/override")
    async def override(bay_id: str, body: OverrideIn):
        return await run(k.override_bay, bay_id, body.action, body.ticket_id, body.staff_id, body.confirm)

    # ---- audit ----
    @app.get("/event-log")
    async def event_log(limit: int = 500):
        return await asyncio.to_thread(k.event_log, limit)

    @app.get("/observations")
    async def observations(limit: int = 500):
        return await asyncio.to_thread(k.observations, limit)

    return app


def main() -> None:
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser(description="dig-in kitchen backend")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8002)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(create_app(load_settings(args.config)), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
