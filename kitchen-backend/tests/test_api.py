"""HTTP layer + context push to CV (BACKEND_SPEC 4, 5, 10)."""
import asyncio
import json

import httpx
import pytest

from kbackend.app import create_app
from kbackend.cvlink import ContextPusher
from kbackend.db import connect
from kbackend.service import Kitchen
from tests.conftest import make_settings


class FakeCV:
    def __init__(self):
        self.calls = []
        self.up = True
        self.boot = "boot-1"

    def handler(self, request: httpx.Request) -> httpx.Response:
        if not self.up:
            raise httpx.ConnectError("down")
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, body))
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok", "boot_id": self.boot})
        return httpx.Response(200, json={"ok": True})

    def last(self, method, path):
        for m, p, b in reversed(self.calls):
            if m == method and p == path:
                return b
        return None


@pytest.fixture
def fake_cv():
    return FakeCV()


@pytest.fixture
def env(clock, fake_cv):
    s = make_settings()
    k = Kitchen(s, connect(":memory:"), clock=clock)
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake_cv.handler), base_url="http://cv")
    pusher = ContextPusher(k, "http://cv", client=client, health_interval_s=0.05, max_backoff_s=0.1)
    app = create_app(s, k, pusher)
    return app, k, pusher


async def until(pred, timeout=2.0):
    for _ in range(int(timeout / 0.02)):
        if pred():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("timeout")


async def test_http_flow_and_context_push(env, fake_cv, cv):
    app, k, pusher = env
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://be") as c:
            r = await c.post("/tickets", json={"table": "12", "course": "main", "plates_expected": 1})
            assert r.status_code == 201
            tid = r.json()["id"]
            await until(lambda: (fake_cv.last("PUT", "/context/bays") or {}).get("bays", {}).get("A"))
            assert fake_cv.last("PUT", "/context/bays")["bays"]["A"]["ticket_id"] == tid
            assert set(fake_cv.last("PUT", "/context/bays")["bays"]) == {"A", "B", "C"}  # full replace

            r = await c.post("/cv/events", json=cv.arrived("A", 0, 1, expected=1))
            assert r.json()["accepted"]
            task = (await c.get("/tasks")).json()[0]
            r = await c.post(f"/tasks/{task['id']}/claim", json={"server_id": "s1"})
            assert r.status_code == 200
            await until(lambda: (fake_cv.last("PUT", "/context/claims") or {}).get("claims", {}).get("A"))
            r = await c.post(f"/tasks/{task['id']}/claim", json={"server_id": "s2"})
            assert r.status_code == 409 and r.json()["claimed_by"] == "s1"

            r = await c.put("/active-ticket", json={"ticket_id": tid, "set_by": "cook_voice"})
            assert r.status_code == 200
            await until(lambda: fake_cv.last("PUT", "/context/active_ticket") is not None)
            assert fake_cv.last("PUT", "/context/active_ticket")["ticket_id"] == tid
            await c.delete("/active-ticket")
            await until(lambda: any(m == "DELETE" and p == "/context/active_ticket" for m, p, _ in fake_cv.calls))

            st = (await c.get("/state")).json()
            assert st["cv_link"]["up"] and st["tickets"][0]["status"] == "ready"
            assert (await c.post("/tickets/NOPE/ready")).status_code == 404


async def test_malformed_422_and_batch(env, cv):
    app, k, _ = env
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://be") as c:
            r = await c.post("/cv/events", json={"type": "PLATE_ARRIVED"})
            assert r.status_code == 422
            good = cv.heartbeat()
            r = await c.post("/cv/events", json=[good, {"bad": 1}, good])
            body = r.json()
            assert r.status_code == 200 and body["accepted"] == [good["event_id"]]
            assert body["duplicates"] == [good["event_id"]] and len(body["rejected"]) == 1


async def test_push_failure_retries_and_repush_on_cv_restart(env, fake_cv):
    app, k, pusher = env
    fake_cv.up = False
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://be") as c:
            r = await c.post("/tickets", json={"table": "1"})
            assert r.status_code == 201  # state change committed even though CV is down
            await asyncio.sleep(0.2)
            assert pusher.pushed_version != k.context_version
            fake_cv.up = True
            await until(lambda: pusher.pushed_version == k.context_version)
            n = len([c for c in fake_cv.calls if c[1] == "/context/bays"])
            fake_cv.boot = "boot-2"  # CV restarted -> lost its context
            await until(lambda: len([c for c in fake_cv.calls if c[1] == "/context/bays"]) > n)


async def test_zone_resolve_forwarded(env, fake_cv):
    app, k, pusher = env
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://be") as c:
            r = await c.post("/inventory/Z1/restock", json={"qty": 2})
            assert r.json()["on_hand"] == 10
            await until(lambda: fake_cv.last("POST", "/zones/Z1/resolve") == {"count": 10})
            assert k.cv_calls == []


async def test_websocket_gets_snapshot_and_updates(env, cv):
    from starlette.testclient import TestClient
    app, k, _ = env
    with TestClient(app) as tc:
        with tc.websocket_connect("/ws") as ws:
            first = ws.receive_json()
            assert first["kind"] == "state"
            tc.post("/tickets", json={"table": "9"})
            kinds = {ws.receive_json()["kind"] for _ in range(2)}
            assert kinds & {"ticket", "bay"}
