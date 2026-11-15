"""Factory avoids a second Restaurant and keeps app/auth composition at the root."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, Header, HTTPException
from pydantic import ValidationError

from app.coordination.rules import Conflict
from app.mvp.cv_bridge import CVBridge, CVEnvelope

log = logging.getLogger(__name__)


def create_cv_router(restaurant_provider):
    bridge = CVBridge(restaurant_provider)

    async def watchdog():
        while True:
            await asyncio.sleep(1)
            try:
                await asyncio.to_thread(bridge.expire)
            except Exception:
                log.exception(
                    "CV heartbeat watchdog failed; manual recovery remains available"
                )

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(watchdog())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    router = APIRouter(
        prefix="/api/v2/cv", tags=["Canonical CV bridge"], lifespan=lifespan
    )

    @router.get("/context")
    def context(x_demo_session: str = Header(default="")):
        try:
            return bridge.context(x_demo_session)
        except Conflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/observations")
    def observe(body: CVEnvelope, x_demo_session: str = Header(default="")):
        try:
            return bridge.receive(body, x_demo_session)
        except Conflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="Invalid CV producer event/evidence"
            ) from exc

    return router
