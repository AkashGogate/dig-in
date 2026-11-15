"""Actual team producer models -> canonical Restaurant; no pixel/camera access."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.coordination.rules import Conflict
from app.mvp.contracts import Command
from app.mvp.cv_api import create_cv_router
from app.mvp.cv_bridge import CVBridge, CVEnvelope
from app.mvp.domain import Restaurant


@pytest.fixture
def demo():
    core = Restaurant()
    sessions = {
        actor: core.session(actor)["session_id"]
        for actor in ("server-1", "cook-1", "lead-1")
    }
    return core, sessions


def execute(demo, payload, actor="server-1"):
    return demo[0].execute(
        Command(event_id=str(uuid4()), payload=payload), demo[1][actor]
    )


def order(demo, quantity=1):
    key = execute(demo, {"action": "start_order", "table_id": "1"})["result"][
        "order_id"
    ]
    result = execute(
        demo,
        {
            "action": "edit_draft",
            "order_id": key,
            "revision": 1,
            "table_id": "1",
            "lines": [{"id": "dish", "menu_id": "salmon", "quantity": quantity}],
        },
    )
    execute(
        demo,
        {
            "action": "confirm_send",
            "order_id": key,
            "revision": result["result"]["revision"],
            "human_confirmed": True,
        },
    )
    execute(demo, {"action": "acknowledge", "order_id": key}, "cook-1")
    return key


def packet(demo, occupied=True, *, zone_id="A", at=None):
    zone = demo[0].state.zones[zone_id]
    return CVEnvelope(
        event={
            "event_id": str(uuid4()),
            "type": "BAY_STATE",
            "source": "cv.plating",
            "camera_id": "plating_cam",
            "observed_at": (at or datetime.now(UTC)).isoformat(),
            "bay_id": zone_id,
            "attribution": {
                "ticket_id": zone.order_id,
                "method": "bay_assignment" if zone.order_id else "none",
            },
            "payload": {
                "plate_count": int(occupied),
                "occupied": occupied,
                "assigned_ticket_id": zone.order_id,
                "assigned_table": "1" if zone.order_id else None,
                "assigned_course": None,
            },
        },
        run_id="synthetic-bridge-test",
        simulated=True,
        binding={
            "zone_id": zone.id,
            "order_id": zone.order_id,
            "dish_id": zone.dish_id,
            "assignment_version": zone.assignment_version,
        },
        evidence={"stable_ms": 1600, "hand_present": False},
    )


def health(state="ok", at=None):
    return CVEnvelope(
        event={
            "event_id": str(uuid4()),
            "type": "CAMERA_STATUS",
            "source": "cv.plating",
            "camera_id": "plating_cam",
            "observed_at": (at or datetime.now(UTC)).isoformat(),
            "payload": {
                "state": state,
                "reason": None,
                "since": datetime.now(UTC).isoformat(),
            },
        },
        run_id="synthetic-bridge-test",
        simulated=True,
    )


def test_real_producer_schema_ready_partial_pickup_fifo_and_exact_retry(demo):
    key = order(demo, 2)
    bridge = CVBridge(lambda: demo[0])
    token = demo[1]["cook-1"]
    body = packet(demo)
    first = bridge.receive(body, token)
    assert first["replayed"] is False
    assert bridge.receive(body, token)["replayed"] is True
    assert demo[0].state.orders[key].ready_notified is False
    assert sum(d.ready_at is not None for d in demo[0].state.dishes.values()) == 1
    bridge.receive(packet(demo, False), token)
    assert demo[0].state.dishes[body.binding.dish_id].stage == "picked_up"
    assert demo[0].state.zones["A"].dish_id is None
    bridge.receive(packet(demo, zone_id="B"), token)
    assert demo[0].state.orders[key].ready_notified is True
    assert len(demo[0].state.notifications) == 1
    assert all(
        e.simulated and e.run_id == body.run_id
        for e in demo[0].state.events
        if e.source == "camera"
    )


def test_whole_envelope_and_capture_version_cannot_change_on_retry(demo):
    order(demo)
    bridge = CVBridge(lambda: demo[0])
    token = demo[1]["cook-1"]
    body = packet(demo)
    bridge.receive(body, token)
    changed = body.model_copy(deep=True)
    changed.event["confidence"] = 0.1
    with pytest.raises(Conflict, match="different evidence"):
        bridge.receive(changed, token)
    bridge.receive(packet(demo, False), token)
    stale = body.model_copy(deep=True)
    stale.event["event_id"] = str(uuid4())
    with pytest.raises(Conflict, match="Stale or mismatched"):
        bridge.receive(stale, token)


@pytest.mark.parametrize("change", ["hand", "unstable", "blocked"])
def test_unstable_hand_and_bad_health_never_make_ready(demo, change):
    order(demo)
    bridge = CVBridge(lambda: demo[0])
    token = demo[1]["cook-1"]
    body = packet(demo)
    if change == "hand":
        body.evidence.hand_present = True
    elif change == "unstable":
        body.evidence.stable_ms = 800
    else:
        bridge.receive(health("degraded"), token)
    result = bridge.receive(body, token)
    assert result["result"]["outcome"] == "ignored"
    assert next(iter(demo[0].state.dishes.values())).stage == "queued"
    if change == "blocked":
        assert demo[0].state.zones["A"].occupancy == "unknown"


def test_missing_proof_multiple_plates_and_recovery_recounts_are_rejected(demo):
    order(demo)
    bridge = CVBridge(lambda: demo[0])
    token = demo[1]["cook-1"]
    for reason in ("missing", "multiple", "recovery"):
        body = packet(demo)
        if reason == "missing":
            body.evidence = None
        elif reason == "multiple":
            body.event["payload"]["plate_count"] = 2
        else:
            body.event["payload"]["note"] = "post_obstruction_recount"
        with pytest.raises(Conflict):
            bridge.receive(body, token)
    assert next(iter(demo[0].state.dishes.values())).stage == "queued"


def test_unknown_camera_timestamp_mismatch_and_unexpected_plate(demo):
    bridge = CVBridge(lambda: demo[0])
    token = demo[1]["cook-1"]
    body = packet(demo, at=datetime.now(UTC) - timedelta(seconds=30))
    with pytest.raises(Conflict, match="timestamp"):
        bridge.receive(body, token)
    body = packet(demo)
    body.event["camera_id"] = "ingredient_cam"
    with pytest.raises(Conflict, match="mismatch"):
        bridge.receive(body, token)
    result = bridge.receive(packet(demo), token)
    assert result["result"]["outcome"] == "unexpected"
    assert demo[0].state.zones["A"].needs_review


def test_ingredient_trip_is_review_evidence_never_recipe_stock_deduction(demo):
    bridge = CVBridge(lambda: demo[0])
    token = demo[1]["cook-1"]
    before = demo[0].snapshot()
    body = CVEnvelope(
        event={
            "event_id": str(uuid4()),
            "type": "INGREDIENT_TRIP",
            "source": "cv.ingredient",
            "camera_id": "ingredient_cam",
            "observed_at": datetime.now(UTC).isoformat(),
            "zone_id": "salmon",
            "payload": {"ingredient": "salmon", "duration_s": 1.0},
        },
        run_id="trip",
        simulated=True,
    )
    assert bridge.receive(body, token)["outcome"] == "review_required"
    assert bridge.receive(body, token)["replayed"]
    assert demo[0].snapshot() == before


def test_watchdog_loss_unknown_preserves_assignments_and_old_health_cannot_recover(
    demo,
):
    order(demo)
    now = datetime.now(UTC)
    clock = [0.0]
    bridge = CVBridge(lambda: demo[0], clock=lambda: clock[0], now=lambda: now)
    token = demo[1]["cook-1"]
    bridge.receive(health(at=now), token)
    clock[0] = 11
    bridge.expire()
    assert demo[0].state.cameras["plating-cam"].status == "offline"
    assert (
        demo[0].state.zones["A"].occupancy == "unknown"
        and demo[0].state.zones["A"].dish_id
    )
    with pytest.raises(Conflict, match="Out-of-order"):
        bridge.receive(health(at=now - timedelta(seconds=1)), token)
    events = len(demo[0].state.events)
    bridge.expire()
    assert len(demo[0].state.events) == events


def test_router_uses_same_core_and_validates_actor_without_any_second_store(demo):
    app = FastAPI()
    app.include_router(create_cv_router(lambda: demo[0]))
    with TestClient(app) as client:
        assert client.get("/api/v2/cv/context").status_code == 409
        assert (
            client.get(
                "/api/v2/cv/context", headers={"X-Demo-Session": demo[1]["server-1"]}
            ).status_code
            == 409
        )
        response = client.get(
            "/api/v2/cv/context", headers={"X-Demo-Session": demo[1]["cook-1"]}
        )
        assert (
            response.status_code == 200
            and response.json()["stable_ms_required"] == 1500
        )
        assert len(response.json()["zones"]) == 6


def test_low_confidence_count_cannot_become_full_confidence_ready(demo):
    order(demo)
    bridge = CVBridge(lambda: demo[0])
    body = packet(demo)
    body.event["confidence"] = 0.1
    with pytest.raises(Conflict, match="confidence"):
        bridge.receive(body, demo[1]["cook-1"])
    assert next(iter(demo[0].state.dishes.values())).stage == "queued"


def test_explicit_tap_pickup_is_a_new_recovery_context_token(demo):
    order(demo)
    bridge = CVBridge(lambda: demo[0])
    token = demo[1]["cook-1"]
    occupied = packet(demo)
    bridge.receive(occupied, token)
    before = bridge.context(token)["zones"]["A"]["reconciliation_id"]
    bridge.receive(health("obstructed"), token)
    execute(demo, {"action": "pickup_dish", "dish_id": occupied.binding.dish_id})
    after = bridge.context(token)["zones"]["A"]["reconciliation_id"]
    assert after and after != before
