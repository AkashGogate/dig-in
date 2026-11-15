import asyncio

import httpx
import pytest

from cvsvc.api import create_app
from cvsvc.config import CVConfig
from cvsvc.main import build_runtime


@pytest.fixture
def rt(tmp_path):
    cfg = CVConfig(events_log_path=str(tmp_path / "events.jsonl"))
    rt = build_runtime(cfg, mock=True, mock_auto=False, seed=1)
    rt.mock.tick_s = 0.01
    rt.mock.plate_interval_s = 0.0
    rt.mock.pickup_after_claim_s = 0.0
    return rt


async def wait_for(pred, timeout=2.0):
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        if pred():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not met")


async def test_mock_reacts_to_context(rt, tmp_path):
    app = create_app(rt)
    async with app.router.lifespan_context(app):
        rt.mock.auto_plating = True
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://cv") as c:
            r = await c.put("/context/bays", json={"bays": {"A": {"ticket_id": "T-1", "table": "12",
                                                                   "course": "main", "expected_plates": 2}}})
            assert r.status_code == 200

            def types():
                return [e["type"] for e in rt.bus.recent if e.get("bay_id") == "A"]

            await wait_for(lambda: types().count("PLATE_ARRIVED") == 2)
            arrivals = [e for e in rt.bus.recent if e["type"] == "PLATE_ARRIVED"]
            assert [a["payload"]["count_matches_expected"] for a in arrivals] == [False, True]
            assert arrivals[0]["attribution"] == {"ticket_id": "T-1", "method": "bay_assignment", "ambiguous": False}

            await c.put("/context/claims", json={"claims": {"A": {"task_id": "RUN-9", "server_id": "s1"}}})
            await wait_for(lambda: "PLATE_REMOVED" in types())
            rem = [e for e in rt.bus.recent if e["type"] == "PLATE_REMOVED"][-1]
            assert rem["payload"]["claimed_task_id"] == "RUN-9" and rem["payload"]["bay_now_empty"]

            st = (await c.get("/state")).json()
            assert st["bays"]["A"]["plate_count"] == 0
            assert st["context"]["claims"]["A"]["task_id"] == "RUN-9"
            recent = (await c.get("/events/recent", params={"n": 5})).json()
            assert len(recent) == 5
    assert (tmp_path / "events.jsonl").read_text().count("\n") >= 5


async def test_obstruction_blocks_plate_events(rt):
    app = create_app(rt)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://cv") as c:
            await c.post("/mock/cameras/plating_cam", json={"state": "obstructed", "reason": "lens_covered"})
            n = len(rt.bus.recent)
            await c.post("/mock/bays/B/plates", json={"delta": 1})
            assert all(e["type"] == "CAMERA_STATUS" for e in list(rt.bus.recent)[n:])
            await c.post("/mock/cameras/plating_cam", json={"state": "ok"})
            recount = [e for e in rt.bus.recent if e["type"] == "BAY_STATE" and e["bay_id"] == "B"][-1]
            assert recount["payload"]["plate_count"] == 1
            assert recount["payload"]["note"] == "post_obstruction_recount"


async def test_resolve_zone(rt):
    app = create_app(rt)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://cv") as c:
            r = await c.post("/zones/Z1/resolve", json={"count": 3})
            assert r.json()["count"] == 3
            assert (await c.post("/zones/NOPE/resolve", json={"count": 3})).status_code == 404
            assert (await c.get("/state")).json()["zones"]["Z1"]["count"] == 3
