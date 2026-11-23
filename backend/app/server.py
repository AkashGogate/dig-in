"""Application composition: one Menu/Core, service journeys and CV/voice adapters.

Legacy scenario/log routes remain isolated for regression demos. Paid microphone
capture is available only through the bounded, deliberate v2 voice relay.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

# Module loggers (e.g. app.mvp.api) are silent under Python's default root
# config; this makes their curl-verifiable action logs actually reach stdout.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

from app.call_parser import parse_call
from app.coordination.api import router as coordination_router
from app.demo_auth import DemoAccessMiddleware, require_demo_auth
from app.log_store import init_db, make_session_factory, write_result
from app.mismatch import check_mismatch
from app.mvp import api as mvp_api
from app.mvp.api import export_loop
from app.mvp.api import router as mvp_router
from app.mvp.cv_api import create_cv_router
from app.session import KitchenSession, SessionLimitExceeded
from app.ticket_queue import TicketQueue

engine, SessionFactory = make_session_factory()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(engine)
    exporter = asyncio.create_task(export_loop())
    try:
        yield
    finally:
        exporter.cancel()
        try:
            await exporter
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)
app.include_router(coordination_router)
app.include_router(mvp_router)
app.include_router(create_cv_router(lambda: mvp_api.restaurant))
app.add_middleware(DemoAccessMiddleware)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "schema_version": 2}


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        v.strip()
        for v in os.environ.get(
            "DIG_IN_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if v.strip()
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ponytail: one in-memory queue per demo session id; fine for a single-instance demo.
_queues: dict[str, TicketQueue] = {}
_active: dict[str, KitchenSession] = {}


def _client_ip(request_or_ws) -> str:
    return request_or_ws.client.host if request_or_ws.client else "unknown"


@app.post("/session/start", dependencies=[Depends(require_demo_auth)])
async def start_session(request: Request):
    client_ip = _client_ip(request)
    session_id = str(uuid.uuid4())
    try:
        session = KitchenSession(session_id, client_ip)
    except SessionLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    _active[session_id] = session
    _queues[session_id] = TicketQueue()
    return {"session_id": session_id, "max_seconds": session.seconds_remaining()}


@app.post("/session/{session_id}/kill")
async def kill_session(session_id: str):
    session = _active.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")
    session.close()
    _active.pop(session_id, None)
    _queues.pop(session_id, None)
    return {"killed": True}


def _fixture_path() -> str:
    import pathlib

    return str(
        pathlib.Path(__file__).resolve().parent.parent
        / "tests"
        / "fixtures"
        / "transcripts.json"
    )


@app.get("/scenarios")
async def list_scenarios():
    """Backs the demo UI's 'Play a test scenario' button (DEMO_PLAN.md #4)."""
    with open(_fixture_path()) as f:
        data = json.load(f)
    return [{"name": c["name"], "description": c["description"]} for c in data]


@app.websocket("/ws/{session_id}")
async def call_log_ws(websocket: WebSocket, session_id: str):
    """Streams parsed/mismatch-checked calls to the frontend live log (USER_FLOW.md #9).

    Accepts either {"type": "transcript", "text": ..., "speaker_turn": ...} for a
    live-mic client-side-transcribed turn, or {"type": "scenario", "name": ...}
    to replay a fixture scenario through the same parse->mismatch->log path.
    """
    session = _active.get(session_id)
    if session is None:
        await websocket.close(code=4404, reason="unknown session")
        return

    await websocket.accept()
    queue = _queues[session_id]

    async def _emit_result(call, result):
        async with SessionFactory() as db_session:
            await write_result(db_session, result)
        await websocket.send_json(
            {
                "raw_text": call.raw_text,
                "item": call.item,
                "quantity": call.quantity,
                "station": call.station,
                "speaker_turn": call.speaker_turn,
                "is_call": call.is_call,
                "matched": result.matched,
                "reason": result.reason,
                "ticket_id": result.ticket_id,
            }
        )

    try:
        while not session.expired():
            msg = await websocket.receive()

            if msg.get("type") == "websocket.disconnect":
                break

            if "bytes" in msg and msg["bytes"] is not None:
                # Legacy scenarios remain inspectable, but all paid microphone
                # capture goes through the bounded, privacy-controlled v2 relay.
                await websocket.send_json(
                    {
                        "error": "Legacy live audio is disabled. Use Server or Kitchen voice."
                    }
                )
                continue

            if "text" not in msg or msg["text"] is None:
                continue
            payload = json.loads(msg["text"])

            if payload.get("type") == "scenario":
                with open(_fixture_path()) as f:
                    scenarios = {c["name"]: c for c in json.load(f)}
                scenario = scenarios.get(payload["name"])
                if scenario is None:
                    await websocket.send_json(
                        {"error": f"unknown scenario {payload['name']!r}"}
                    )
                    continue
                for turn in scenario["turns"]:
                    call = parse_call(turn["text"], speaker_turn=turn["speaker_turn"])
                    result = check_mismatch(call, queue)
                    await _emit_result(call, result)
    except WebSocketDisconnect:
        pass
    finally:
        session.close()
        _active.pop(session_id, None)
        _queues.pop(session_id, None)
