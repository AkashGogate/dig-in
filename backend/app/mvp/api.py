"""MVP API; demo sessions are identity simulation, not production auth."""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response

from app.analytics.events import CanonicalEvent
from app.analytics.outbox import FakeAdapter, JsonlAdapter
from app.coordination.rules import Conflict
from app.mvp import contracts as c
from app.mvp.domain import Restaurant
from app.mvp.menu import MenuDocument, import_status
from app.mvp.menu_embeddings import EmbeddingError
from app.mvp.menu_extraction import (
    MAX_UPLOAD,
    ExtractionUnavailable,
    extract_menu,
    extraction_status,
)
from app.mvp.menu_import import MenuPrepareRequest, MenuSearchRequest
from app.mvp.service_contracts import Audience, ServiceSummary
from app.mvp.voice import adapter_status
from app.mvp.voice_live import make_router as make_voice_router

router = APIRouter(prefix="/api/v2", tags=["MVP v2"])
logger = logging.getLogger(__name__)
restaurant = Restaurant()


def pinned_voice_menu(body, session_id):
    with restaurant.lock:
        if session_id not in restaurant.sessions:
            raise HTTPException(409, "Select a demo session before voice capture")
        if body and body.order_id:
            if session_id not in restaurant.sessions:
                raise HTTPException(409, "Select a demo session before voice capture")
            order = restaurant.state.orders.get(body.order_id)
            if (
                order is None
                or order.status != "draft"
                or order.owner != restaurant.sessions[session_id]
            ):
                raise HTTPException(
                    409, "Capture must target your current editable draft"
                )
            if body.menu_revision != order.menu_revision:
                raise HTTPException(
                    409, "Draft menu revision changed; refresh before capture"
                )
            return restaurant.state.menus[order.menu_revision].model_copy(deep=True)
        if body and body.menu_revision:
            if session_id not in restaurant.sessions or restaurant.state.actors[
                restaurant.sessions[session_id]
            ].role not in ("cook", "lead"):
                raise HTTPException(
                    409, "Kitchen session required for menu-scoped capture"
                )
            if body.menu_revision not in restaurant.state.menus:
                raise HTTPException(409, "Unknown menu revision")
            return restaurant.state.menus[body.menu_revision].model_copy(deep=True)
        return restaurant.state.menu.model_copy(deep=True)


router.include_router(
    make_voice_router(lambda: restaurant.state.menu, pinned_voice_menu)
)


def checked(fn):
    try:
        return fn()
    except Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/state", response_model=c.Snapshot)
def state():
    return restaurant.snapshot()


@router.post("/sessions")
def sessions(body: c.SessionRequest):
    result = checked(lambda: restaurant.session(body.actor_id))
    logger.info("session_start actor_id=%s session_id=%s", body.actor_id, result["session_id"])
    return result


@router.post("/commands", response_model=c.CommandResponse)
def commands(body: c.Command, x_demo_session: str = Header(default="")):
    result = checked(lambda: restaurant.execute(body, x_demo_session))
    logger.info("command session=%s action=%s result=%s", x_demo_session, body.payload.action, result["result"])
    return result


@router.get("/service/summary", response_model=ServiceSummary)
def service_summary(audience: Audience, x_demo_session: str = Header(default="")):
    return checked(lambda: restaurant.service_summary(x_demo_session, audience))


@router.get("/contracts")
def contracts():
    return {
        "schema_version": 2,
        "menu": MenuDocument.model_json_schema(),
        "menu_prepare": MenuPrepareRequest.model_json_schema(),
        "menu_search": MenuSearchRequest.model_json_schema(),
        "service_summary": ServiceSummary.model_json_schema(),
        "command": c.Command.model_json_schema(),
        "state": c.Snapshot.model_json_schema(),
        "event": CanonicalEvent.model_json_schema(),
    }


@router.get("/menu")
def menu():
    with restaurant.lock:
        return restaurant.state.menu.model_copy(deep=True)


@router.post("/menu/match")
def match(body: c.MatchRequest):
    return restaurant.match_menu(body.text)


@router.get("/menu/extraction-status")
def menu_extraction_status():
    return extraction_status()


@router.post("/menu/extract")
async def extract_menu_document(
    request: Request, x_demo_session: str = Header(default="")
):
    # Authorize before accepting file bytes. OCR/provider I/O never owns Core's lock.
    with restaurant.lock:
        checked(lambda: restaurant._menu_lead(x_demo_session))
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_UPLOAD:
            raise HTTPException(status_code=413, detail="Menu upload exceeds 8 MiB")
    media_type = request.headers.get("content-type", "").split(";")[0]
    try:
        return await asyncio.to_thread(extract_menu, bytes(content), media_type)
    except ExtractionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Document extraction failed. Use a readable PDF (1–10 unlocked pages), PNG or JPEG, or paste the menu text.",
        ) from exc
    finally:
        content.clear()


@router.post("/menu/prepare")
def prepare_menu(body: MenuPrepareRequest, x_demo_session: str = Header(default="")):
    try:
        return checked(lambda: restaurant.prepare_menu(body, x_demo_session))
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        # Validation errors may contain input excerpts; never echo raw content.
        raise HTTPException(
            status_code=422,
            detail="Invalid menu input; check the documented format, unique IDs and field bounds",
        ) from exc


@router.get("/menu/index")
def menu_index():
    with restaurant.lock:
        return restaurant.menu_indexes[restaurant.state.menu_revision].status()


@router.post("/menu/search")
def search_menu(body: MenuSearchRequest, x_demo_session: str = Header(default="")):
    # Require a demo session before any potential provider cost; not real auth.
    def search():
        with restaurant.lock:
            if x_demo_session not in restaurant.sessions:
                raise Conflict("Select a demo staff/device session")
        return restaurant.search_menu(body.text, body.menu_revision, body.limit)

    try:
        return checked(search)
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/menu/import-status")
def menu_import_status():
    return import_status(restaurant.state.menu)


@router.get("/voice/status")
def voice_status():
    return adapter_status()


@router.get("/events")
def events(format: str = "json"):
    rows = restaurant.snapshot()["events"]
    if format == "jsonl":
        import json

        return Response(
            "".join(json.dumps(row) + "\n" for row in rows),
            media_type="application/x-ndjson",
        )
    return rows


@router.post("/events", response_model=c.CommandResponse)
def ingest_event(body: CanonicalEvent, x_demo_session: str = Header(default="")):
    """Canonical adapter intent ingress, still subject to authoritative rules.

    A requested dish.ready is not an accepted fact until stable evidence validates.
    The returned events expose accepted/observed outcome; rejection is HTTP 409.
    Incoming `received_at` is not used as server receipt time.
    """
    p = body.payload
    if body.type in ("dish.ready", "dish.picked_up") and body.source == "camera":
        zone = restaurant.state.zones.get(p.get("zone_id"))
        if zone is not None and (
            (body.order_id is not None and body.order_id != zone.order_id)
            or (body.dish_id is not None and body.dish_id != zone.dish_id)
        ):
            raise HTTPException(
                status_code=409,
                detail="Camera correlation targets do not match zone assignment",
            )
        payload = {
            "action": "zone_observation",
            "zone_id": p.get("zone_id"),
            "assignment_version": p.get("assignment_version"),
            "occupied": body.type == "dish.ready",
            "stable_ms": p.get("stable_ms", 0),
            "hand_present": p.get("hand_present", False),
        }
    elif body.type in ("dish.ready", "dish.picked_up", "dish.started"):
        payload = {
            "action": {
                "dish.ready": "ready_dish",
                "dish.picked_up": "pickup_dish",
                "dish.started": "start_dish",
            }[body.type],
            "dish_id": body.dish_id,
            "fallback_reason": p.get("fallback_reason"),
        }
    elif body.type in ("order.acknowledged", "order.delivered"):
        payload = {
            "action": "acknowledge"
            if body.type == "order.acknowledged"
            else "deliver_order",
            "order_id": body.order_id,
        }
    elif body.type == "order.submitted":
        payload = {
            "action": "confirm_send",
            "order_id": body.order_id,
            "revision": p.get("revision"),
            "human_confirmed": p.get("human_confirmed", False),
        }
    elif body.type == "camera.status":
        payload = {
            "action": "camera_status",
            "camera_id": p.get("camera_id"),
            "status": p.get("status"),
            "reason": p.get("reason", "Adapter reported status"),
        }
    elif body.type == "stock.changed" and body.source == "camera":
        payload = {
            "action": "stock_observation",
            "zone_id": p.get("zone_id"),
            "delta": p.get("delta"),
            "stable_ms": p.get("stable_ms", 0),
            "hand_present": p.get("hand_present", False),
        }
    else:
        raise HTTPException(
            status_code=422,
            detail="Unsupported incoming event intent; use the documented command interface",
        )
    from pydantic import ValidationError

    try:
        command = c.Command(
            event_id=body.event_id,
            source=body.source,
            time=body.time,
            device_id=body.actor,
            run_id=body.run_id,
            simulated=body.simulated,
            payload=payload,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = checked(lambda: restaurant.execute(command, x_demo_session))
    logger.info("event_ingest session=%s type=%s action=%s result=%s", x_demo_session, body.type, payload["action"], result["result"])
    return result


@router.get("/analytics/health")
def analytics_health():
    return restaurant.outbox.health()


@router.get("/analytics/pending")
def analytics_pending():
    return restaurant.outbox.pending()


async def export_loop():
    """Background export: failures stay pending; operational requests never wait."""
    mode = os.environ.get("DIG_IN_ANALYTICS_MODE", "fake")
    if mode == "disabled":
        return
    if mode not in ("fake", "jsonl"):
        raise ValueError(
            "DIG_IN_ANALYTICS_MODE supports fake/jsonl/disabled only; no live Databricks adapter"
        )
    adapter = (
        JsonlAdapter(
            os.environ.get("DIG_IN_ANALYTICS_JSONL", "outputs/mvp-events.jsonl")
        )
        if mode == "jsonl"
        else FakeAdapter(int(os.environ.get("DIG_IN_ANALYTICS_FAKE_FAILURES", "0")))
    )
    while True:
        await asyncio.to_thread(restaurant.outbox.drain, adapter)
        await asyncio.sleep(1)
