"""MVP API; demo sessions are identity simulation, not production auth."""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response

from app.analytics.events import CanonicalEvent
from app.analytics.outbox import FakeAdapter, JsonlAdapter
from app.coordination.rules import Conflict
from app.mvp import contracts as c
from app.mvp.domain import Restaurant
from app.mvp.menu import import_status, match_menu
from app.mvp.voice import adapter_status
from app.mvp.voice_live import make_router as make_voice_router

router = APIRouter(prefix="/api/v2", tags=["MVP v2"])
restaurant = Restaurant()
router.include_router(make_voice_router(lambda: restaurant.state.menu))


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
    return checked(lambda: restaurant.session(body.actor_id))


@router.post("/commands", response_model=c.CommandResponse)
def commands(body: c.Command, x_demo_session: str = Header(default="")):
    return checked(lambda: restaurant.execute(body, x_demo_session))


@router.get("/contracts")
def contracts():
    return {
        "schema_version": 2,
        "command": c.Command.model_json_schema(),
        "state": c.Snapshot.model_json_schema(),
        "event": CanonicalEvent.model_json_schema(),
    }


@router.get("/menu")
def menu():
    return restaurant.state.menu


@router.post("/menu/match")
def match(body: c.MatchRequest):
    return match_menu(restaurant.state.menu, body.text)


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
    return checked(lambda: restaurant.execute(command, x_demo_session))


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
