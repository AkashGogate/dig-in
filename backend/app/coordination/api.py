"""Demo API. Session selection is explicit but is NOT production authentication."""

from fastapi import APIRouter, Header, HTTPException

from app.coordination.contracts import (
    Command,
    CommandResponse,
    DemoSession,
    SessionResponse,
    Snapshot,
    schema,
)
from app.coordination.domain import Conflict, Restaurant

router = APIRouter(prefix="/api/v1", tags=["coordination demo"])
restaurant = Restaurant()


def conflict(fn):
    try:
        return fn()
    except Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/state", response_model=Snapshot)
def state(section: str | None = None):
    return restaurant.snapshot(section)


@router.get("/contracts")
def contracts():
    return schema()


@router.post("/sessions", response_model=SessionResponse)
def sessions(body: DemoSession):
    return conflict(lambda: restaurant.session(body.actor_id))


@router.post("/commands", response_model=CommandResponse)
def commands(
    body: Command, x_demo_session: str = Header(default=""), section: str | None = None
):
    response = conflict(lambda: restaurant.execute(body, x_demo_session))
    if section is not None:
        response["state"] = restaurant.snapshot(section)
    return response
