"""Canonical sidecar measures dwell and freezes actual source model envelopes."""

import copy

import pytest
from cvsvc.events import EventAdapter
from cvsvc.v2 import EvidenceSampler


def context(version=1, order="order-1", dish="dish-1"):
    return {
        "stable_ms_required": 1500,
        "zones": {
            "A": {
                "zone_id": "A",
                "assignment_version": version,
                "order_id": order,
                "dish_id": dish,
                "table_id": "1",
            }
        },
    }


def feed(sampler, clock, count, duration=1.7, hand=False, health="ok", confidence=0.9):
    for _ in range(round(duration * 10)):
        clock[0] += 0.1
        # Fake context polling is independent from frame timestamps.
        sampler.context_at = clock[0]
        sampler.sample("A", 100 + clock[0], count, hand, health, confidence)


def test_dwell_motion_and_capture_context_are_measured_not_assumed():
    packets = []
    clock = [0.0]
    sampler = EvidenceSampler(packets.append, "test", True, clock=lambda: clock[0])
    sampler.set_context(context())
    feed(sampler, clock, 1, 0.8)
    assert not packets
    feed(sampler, clock, 1, 0.2, hand=True)
    feed(sampler, clock, 1)
    assert len(packets) == 1 and packets[0]["evidence"]["stable_ms"] >= 1500
    assert packets[0]["event"]["confidence"] == 0.9
    EventAdapter.validate_python(packets[0]["event"])
    frozen = copy.deepcopy(packets[0])
    sampler.set_context(context(2, "order-2", "dish-2"))
    feed(sampler, clock, 1)
    assert len(packets) == 1  # old occupied zone cannot ready a new dish
    feed(sampler, clock, 0)
    feed(sampler, clock, 1)
    assert packets[0] == frozen and packets[-1]["binding"]["assignment_version"] == 2


def test_missing_frames_low_confidence_and_recovery_require_review():
    packets = []
    clock = [0.0]
    sampler = EvidenceSampler(packets.append, "test", False, clock=lambda: clock[0])
    sampler.set_context(context())
    feed(sampler, clock, 1, 0.8)
    clock[0] += 2
    feed(sampler, clock, 1, 0.8)
    assert not packets
    feed(sampler, clock, 1, confidence=0.1)
    assert not packets
    sampler.quarantine()
    feed(sampler, clock, 0)
    assert not packets
    reviewed = context()
    reviewed["zones"]["A"]["reconciliation_id"] = "staff-reviewed"
    sampler.set_context(reviewed)
    feed(sampler, clock, 0)
    assert packets[-1]["event"]["payload"]["occupied"] is False
    assert packets[-1]["simulated"] is False


@pytest.mark.asyncio
async def test_individual_terminal_rejection_preserves_next_queued_event(
    tmp_path, monkeypatch
):
    import asyncio

    import httpx
    from cvsvc.config import CVConfig
    from cvsvc.main import build_runtime
    from cvsvc.v2 import CanonicalClient

    monkeypatch.delenv("DEMO_AUTH_USER", raising=False)
    monkeypatch.delenv("DEMO_AUTH_PASS", raising=False)
    rt = build_runtime(
        CVConfig(events_log_path=str(tmp_path / "events.jsonl")),
        mock=True,
        mock_auto=False,
        legacy_delivery=False,
    )
    client = CanonicalClient("http://core", rt, True)
    await client.http.aclose()
    received = []

    def handle(request):
        import json

        body = json.loads(request.content)
        received.append(body)
        return httpx.Response(
            409 if body["event"]["event_id"] == "stale" else 200, json={}
        )

    client.http = httpx.AsyncClient(
        base_url="http://core", transport=httpx.MockTransport(handle)
    )
    client.session = "test-session"
    first = {"event": {"event_id": "stale"}, "binding": {"assignment_version": 1}}
    second = {"event": {"event_id": "valid"}, "binding": {"assignment_version": 2}}
    await client.queue.put(copy.deepcopy(first))
    await client.queue.put(copy.deepcopy(second))
    task = asyncio.create_task(client.deliver())
    try:
        await asyncio.wait_for(client.queue.join(), timeout=2)
        assert received == [first, second]
        assert list(client.reviews) == [{"event_id": "stale", "status": 409}]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.http.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_recovery", [False, True])
async def test_native_cv_mock_evidence_reaches_one_canonical_restaurant(
    tmp_path, monkeypatch, blocked_recovery
):
    import asyncio
    import sys
    from pathlib import Path

    import httpx
    from cvsvc.api import create_app
    from cvsvc.config import BayConfig, CVConfig, PlatingConfig
    from cvsvc.main import build_runtime
    from cvsvc.v2 import CanonicalClient
    from fastapi import FastAPI

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from uuid import uuid4

    from app.mvp import api as core_api
    from app.mvp.contracts import Command
    from app.mvp.cv_api import create_cv_router
    from app.mvp.domain import Restaurant

    monkeypatch.delenv("DEMO_AUTH_USER", raising=False)
    monkeypatch.delenv("DEMO_AUTH_PASS", raising=False)
    core = Restaurant()
    monkeypatch.setattr(core_api, "restaurant", core)
    core_app = FastAPI()
    core_app.include_router(core_api.router)
    core_app.include_router(create_cv_router(lambda: core))
    cfg = CVConfig(
        plating=PlatingConfig(bays=[BayConfig(id=key) for key in "ABCDEF"]),
        events_log_path=str(tmp_path / "events.jsonl"),
    )
    runtime = build_runtime(cfg, mock=True, mock_auto=False, legacy_delivery=False)
    adapter = CanonicalClient("http://core", runtime, True)
    await adapter.http.aclose()
    adapter.http = httpx.AsyncClient(
        base_url="http://core", transport=httpx.ASGITransport(app=core_app)
    )
    runtime.background.append(adapter.run)
    cv_app = create_app(runtime)
    async with (
        core_app.router.lifespan_context(core_app),
        cv_app.router.lifespan_context(cv_app),
        httpx.AsyncClient(
            base_url="http://cv", transport=httpx.ASGITransport(app=cv_app)
        ) as cv,
    ):
        server = core.session("server-1")["session_id"]
        cook = core.session("cook-1")["session_id"]

        def command(payload, session=server):
            return core.execute(
                Command(event_id=str(uuid4()), payload=payload), session
            )

        key = command({"action": "start_order", "table_id": "1"})["result"]["order_id"]
        result = command(
            {
                "action": "edit_draft",
                "order_id": key,
                "revision": 1,
                "table_id": "1",
                "lines": [{"id": "dish", "menu_id": "salmon", "quantity": 1}],
            }
        )
        command(
            {
                "action": "confirm_send",
                "order_id": key,
                "revision": result["result"]["revision"],
                "human_confirmed": True,
            }
        )
        command({"action": "acknowledge", "order_id": key}, cook)

        async def wait_for(predicate):
            end = asyncio.get_running_loop().time() + 5
            while not predicate():
                assert asyncio.get_running_loop().time() < end
                await asyncio.sleep(0.05)

        await wait_for(lambda: adapter.sampler.context is not None)
        response = await cv.post("/mock/bays/A/plates", json={"delta": 1})
        assert response.status_code == 200
        await wait_for(lambda: core.state.orders[key].ready_notified)
        assert len(core.state.notifications) == 1
        if blocked_recovery:
            await cv.post(
                "/mock/cameras/plating_cam",
                json={"state": "obstructed", "reason": "test obstruction"},
            )
            await wait_for(
                lambda: core.state.cameras["plating-cam"].status == "blocked"
            )
            await cv.post("/mock/bays/A/plates", json={"delta": -1})
            await cv.post("/mock/cameras/plating_cam", json={"state": "ok"})
            await wait_for(lambda: core.state.cameras["plating-cam"].status == "ok")
            assert (
                core.state.orders[key].status == "ready"
            )  # no unseen pickup during blockage
            original = next(d for d in core.state.dishes.values() if d.order_id == key)
            command({"action": "pickup_dish", "dish_id": original.id})
            newkey = command({"action": "start_order", "table_id": "2"})["result"][
                "order_id"
            ]
            edited = command(
                {
                    "action": "edit_draft",
                    "order_id": newkey,
                    "revision": 1,
                    "table_id": "2",
                    "lines": [{"id": "next", "menu_id": "salmon", "quantity": 1}],
                }
            )
            command(
                {
                    "action": "confirm_send",
                    "order_id": newkey,
                    "revision": edited["result"]["revision"],
                    "human_confirmed": True,
                }
            )
            command({"action": "acknowledge", "order_id": newkey}, cook)
            await wait_for(
                lambda: any(
                    event.type == "camera.observation"
                    and event.order_id == newkey
                    and event.payload.get("outcome") == "empty_before_ready"
                    for event in core.state.events
                )
            )
            assert core.state.orders[newkey].status == "acknowledged"
            await cv.post("/mock/bays/A/plates", json={"delta": 1})
            await wait_for(lambda: core.state.orders[newkey].ready_notified)
        else:
            response = await cv.post("/mock/bays/A/plates", json={"delta": -1})
            assert response.status_code == 200
            await wait_for(lambda: core.state.orders[key].status == "picked_up")
            assert core.state.zones["A"].dish_id is None
        camera_events = [
            event for event in core.state.events if event.source == "camera"
        ]
        assert camera_events and all(event.simulated for event in camera_events)


def test_camera_mode_requires_empty_reference_before_opening_any_camera(
    tmp_path, monkeypatch
):
    import sys

    from cvsvc import v2
    from cvsvc.config import CameraConfig, CVConfig

    cfg = CVConfig(
        cameras={"plating_cam": CameraConfig()}, calibration_dir=str(tmp_path)
    )
    monkeypatch.setattr(v2, "load_config", lambda _: cfg)
    monkeypatch.setattr(sys, "argv", ["v2", "--camera"])
    with pytest.raises(ValueError, match="Calibrate empty"):
        v2.main()


def test_native_detector_preserves_multiple_plate_overflow():
    from cvsvc.config import BayConfig
    from cvsvc.plating.bays import BayCounter

    from tests.test_pipeline import BAY_POLY, scene

    cfg = BayConfig(
        id="A", polygon=BAY_POLY, min_plate_area_px=4000, max_plate_area_px=20000
    )
    counter = BayCounter(cfg, scene(), max_plates=4)
    result = counter.count(scene(plates=[(440, 310), (570, 405)]))
    assert result.count >= 2  # producer must not clamp two plates into accepted one


def test_strict_pipeline_refuses_first_frame_as_empty_calibration(tmp_path):
    from cvsvc.config import BayConfig, CameraConfig, CVConfig, PlatingConfig
    from cvsvc.context import ContextStore
    from cvsvc.emitter import Emitter
    from cvsvc.events import EventBus
    from cvsvc.pipeline import CameraPipelines

    from tests.test_pipeline import BAY_POLY, scene

    cfg = CVConfig(
        cameras={"cam": CameraConfig()},
        plating=PlatingConfig(camera="cam", bays=[BayConfig(id="A", polygon=BAY_POLY)]),
        calibration_dir=str(tmp_path),
    )
    bus = EventBus()
    ctx = ContextStore()
    pipes = CameraPipelines(cfg, bus, ctx, Emitter(bus.ids, ctx, "cam", "cam"))
    pipes.v2_require_reference = True
    with pytest.raises(ValueError, match="calibrated empty"):
        pipes.workers["cam"]._load_reference(scene(plates=[(470, 350)]))


def test_hand_obscured_empty_cannot_erase_verified_occupied_binding():
    packets = []
    clock = [0.0]
    sampler = EvidenceSampler(packets.append, "test", True, clock=lambda: clock[0])
    sampler.set_context(context())
    feed(sampler, clock, 1)
    assert len(packets) == 1
    feed(sampler, clock, 0, hand=True)
    sampler.set_context(context(2, "order-2", "dish-2"))
    feed(sampler, clock, 1)
    assert len(packets) == 1
    feed(sampler, clock, 0)
    feed(sampler, clock, 1)
    assert packets[-1]["binding"]["dish_id"] == "dish-2"
