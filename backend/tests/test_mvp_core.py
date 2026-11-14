"""MVP v2 API invariants; no hardware, speech provider or cloud credentials."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analytics.outbox import FakeAdapter
from app.mvp import api
from app.mvp.contracts import Command
from app.mvp.domain import Restaurant


@pytest.fixture
def demo(monkeypatch):
    restaurant = Restaurant()
    monkeypatch.setattr(api, "restaurant", restaurant)
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        tokens = {
            actor: client.post("/api/v2/sessions", json={"actor_id": actor}).json()[
                "session_id"
            ]
            for actor in ("server-1", "server-2", "cook-1")
        }
        yield client, tokens, restaurant


def body(payload, source="tap"):
    return Command(
        event_id=str(uuid4()),
        source=source,
        payload=payload,
        run_id="core-test",
        simulated=True,
    ).model_dump(mode="json")


def send(demo, payload=None, *, actor="server-1", source="tap", envelope=None):
    client, tokens, _ = demo
    return client.post(
        "/api/v2/commands",
        headers={"X-Demo-Session": tokens[actor]},
        json=envelope or body(payload, source),
    )


def ok(demo, payload=None, **kwargs):
    response = send(demo, payload, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()


def snapshot(demo):
    response = demo[0].get("/api/v2/state")
    assert response.status_code == 200, response.text
    return response.json()


def order(demo, quantity=1, *, actor="server-1", table="1", menu_id="salmon"):
    order_id = ok(demo, {"action": "start_order", "table_id": table}, actor=actor)[
        "result"
    ]["order_id"]
    edited = ok(
        demo,
        {
            "action": "edit_draft",
            "order_id": order_id,
            "revision": 1,
            "table_id": table,
            "lines": [{"id": "line-one", "menu_id": menu_id, "quantity": quantity}],
        },
        actor=actor,
    )
    revision = edited["state"]["orders"][order_id]["revision"]
    ok(
        demo,
        {
            "action": "confirm_send",
            "order_id": order_id,
            "revision": revision,
            "human_confirmed": True,
        },
        actor=actor,
    )
    return order_id


def ack(demo, order_id):
    return ok(demo, {"action": "acknowledge", "order_id": order_id}, actor="cook-1")


def dish_action(demo, dish_id, action, actor="cook-1", **extra):
    return ok(demo, {"action": action, "dish_id": dish_id, **extra}, actor=actor)


def units(demo, order_id):
    return [
        dish
        for dish in snapshot(demo)["dishes"].values()
        if dish["order_id"] == order_id
    ]


def observe(demo, zone, occupied, **extra):
    return ok(
        demo,
        {
            "action": "zone_observation",
            "zone_id": zone["id"],
            "assignment_version": zone["assignment_version"],
            "occupied": occupied,
            "stable_ms": 1600,
            "hand_present": False,
            **extra,
        },
        actor="cook-1",
        source="camera",
    )


def test_tap_only_without_start_reserves_on_ack_then_delivers(demo):
    key = order(demo)
    before = snapshot(demo)
    assert not any(zone["dish_id"] for zone in before["zones"].values())
    assert before["orders"][key]["status"] == "submitted"
    assigned = ack(demo, key)["state"]
    dish = units(demo, key)[0]
    assert sum(zone["order_id"] == key for zone in assigned["zones"].values()) == 1
    assert dish["stage"] == "queued" and dish["started_at"] is None
    ready = dish_action(demo, dish["id"], "ready_dish")["state"]
    assert ready["dishes"][dish["id"]]["started_at"] is None
    assert ready["orders"][key]["status"] == "ready"
    dish_action(demo, dish["id"], "pickup_dish", actor="server-1")
    delivered = ok(demo, {"action": "deliver_order", "order_id": key})["state"]
    assert delivered["orders"][key]["status"] == "delivered"
    assert not any(zone["dish_id"] for zone in delivered["zones"].values())


def test_quantity_two_has_distinct_zones_and_all_ready_milestone_not_first_plate(demo):
    key = order(demo, quantity=2)
    ack(demo, key)
    first, second = units(demo, key)
    assert first["zone_id"] != second["zone_id"]
    partial = dish_action(demo, first["id"], "ready_dish")["state"]
    assert partial["computed"]["order_progress"][key] == {
        "total": 2,
        "ready": 1,
        "picked_up": 0,
    }
    assert not partial["notifications"]
    dish_action(demo, first["id"], "pickup_dish", actor="server-1")
    completed = dish_action(demo, second["id"], "ready_dish")["state"]
    assert completed["computed"]["order_progress"][key]["ready"] == 2
    assert completed["orders"][key]["status"] == "ready"
    assert len(completed["notifications"]) == 1
    assert sum(event["type"] == "order.ready" for event in completed["events"]) == 1
    duplicate_stage = send(
        demo, {"action": "ready_dish", "dish_id": second["id"]}, actor="cook-1"
    )
    assert duplicate_stage.status_code == 409
    assert len(snapshot(demo)["notifications"]) == 1


def test_concurrent_acknowledgments_allocate_all_or_none_and_retry_when_capacity_frees(
    demo,
):
    first = order(demo, quantity=4)
    second = order(demo, quantity=4, actor="server-2", table="2")
    barrier = Barrier(2)

    def acknowledge(key):
        barrier.wait(timeout=5)
        return ack(demo, key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(acknowledge, [first, second]))
    state = snapshot(demo)
    allocated = [
        key
        for key in (first, second)
        if state["orders"][key]["zone_status"] == "assigned"
    ]
    waiting = [
        key
        for key in (first, second)
        if state["orders"][key]["zone_status"] == "waiting"
    ]
    assert len(allocated) == len(waiting) == 1
    assert (
        sum(zone["order_id"] == allocated[0] for zone in state["zones"].values()) == 4
    )
    assert not any(zone["order_id"] == waiting[0] for zone in state["zones"].values())
    delivered_units = units(demo, allocated[0])
    for dish in delivered_units[:2]:
        dish_action(demo, dish["id"], "ready_dish")
        dish_action(demo, dish["id"], "pickup_dish")
    after = snapshot(demo)
    assert after["orders"][waiting[0]]["zone_status"] == "assigned"
    assert sum(zone["order_id"] == waiting[0] for zone in after["zones"].values()) == 4
    assert (
        len({zone["dish_id"] for zone in after["zones"].values() if zone["dish_id"]})
        == 6
    )
    assert (
        sum(
            event["type"] == "zones.waiting" and event["order_id"] == waiting[0]
            for event in after["events"]
        )
        == 1
    )


def test_camera_stability_hand_and_blocked_feed_do_not_fake_readiness(demo):
    key = order(demo)
    ack(demo, key)
    dish = units(demo, key)[0]
    zone = snapshot(demo)["zones"][dish["zone_id"]]
    for values in ({"stable_ms": 300}, {"hand_present": True}):
        ignored = observe(demo, zone, True, **values)
        assert ignored["state"]["dishes"][dish["id"]]["stage"] == "queued"
        assert ignored["state"]["events"][-1]["type"] == "camera.observation"
        assert ignored["state"]["events"][-1]["outcome"] == "observed"
    ok(
        demo,
        {
            "action": "camera_status",
            "camera_id": zone["camera_id"],
            "status": "blocked",
            "reason": "Covered camera",
        },
        actor="cook-1",
        source="system",
    )
    blocked = observe(demo, zone, False)["state"]
    assert blocked["zones"][zone["id"]]["occupancy"] == "unknown"
    assert blocked["zones"][zone["id"]]["dish_id"] == dish["id"]
    ready = dish_action(
        demo, dish["id"], "ready_dish", fallback_reason="Camera blocked"
    )["state"]
    assert ready["events"][-2]["type"] == "dish.ready"
    assert ready["events"][-2]["payload"]["automation_available"] is False
    dish_action(
        demo,
        dish["id"],
        "pickup_dish",
        actor="server-1",
        fallback_reason="Camera blocked",
    )
    assert snapshot(demo)["dishes"][dish["id"]]["stage"] == "picked_up"


def test_stable_camera_ready_removal_then_stale_assignment_and_unexpected_plate(demo):
    key = order(demo)
    ack(demo, key)
    dish = units(demo, key)[0]
    zone = snapshot(demo)["zones"][dish["zone_id"]]
    # Empty before ready is evidence, never pickup/release.
    empty = observe(demo, zone, False)["state"]
    assert empty["zones"][zone["id"]]["dish_id"] == dish["id"]
    assert empty["dishes"][dish["id"]]["stage"] == "queued"
    ready = observe(demo, zone, True)["state"]
    assert ready["dishes"][dish["id"]]["stage"] == "ready"
    picked = observe(demo, zone, False)["state"]
    assert picked["dishes"][dish["id"]]["stage"] == "picked_up"
    assert (
        picked["zones"][zone["id"]]["assignment_version"] > zone["assignment_version"]
    )
    stale = send(
        demo,
        {
            "action": "zone_observation",
            "zone_id": zone["id"],
            "assignment_version": zone["assignment_version"],
            "occupied": True,
            "stable_ms": 1600,
        },
        actor="cook-1",
        source="camera",
    )
    assert stale.status_code == 409
    free = snapshot(demo)["zones"][zone["id"]]
    unexpected = observe(demo, free, True)["state"]
    assert unexpected["zones"][zone["id"]]["needs_review"] is True
    assert unexpected["events"][-1]["type"] == "zone.unexpected"
    # Returned plate has not changed stock or resurrected the delivered dish.
    assert unexpected["dishes"][dish["id"]]["stage"] == "picked_up"
    assert unexpected["stock_movements"] == []
    reviewed = ok(
        demo,
        {
            "action": "reconcile_zone",
            "zone_id": zone["id"],
            "assignment_version": free["assignment_version"],
            "occupied": False,
            "reason": "Returned empty plate cleared",
        },
        actor="cook-1",
    )["state"]
    assert reviewed["zones"][zone["id"]]["needs_review"] is False


def test_voice_table_unknown_flags_and_human_send_gate(demo):
    key = ok(demo, {"action": "start_order", "table_id": "1"})["result"]["order_id"]
    captured = ok(
        demo,
        {
            "action": "capture_voice",
            "order_id": key,
            "revision": 1,
            "text": "Table 2: one salmon and one dragonfruit",
        },
        source="voice",
    )["state"]
    draft = captured["orders"][key]
    assert {flag["code"] for flag in draft["flags"]} >= {
        "table_mismatch",
        "unknown_item",
    }
    assert len(draft["lines"]) == 1 and draft["lines"][0]["menu_id"] == "salmon"
    assert (
        send(
            demo,
            {
                "action": "confirm_send",
                "order_id": key,
                "revision": draft["revision"],
                "human_confirmed": True,
            },
        ).status_code
        == 409
    )
    for flag in list(draft["flags"]):
        current = snapshot(demo)["orders"][key]
        ok(
            demo,
            {
                "action": "resolve_flag",
                "order_id": key,
                "revision": current["revision"],
                "flag_id": flag["id"],
                "resolution": "keep_selected_table"
                if flag["code"] == "table_mismatch"
                else "reviewed_remove_unknown",
            },
        )
    current = snapshot(demo)["orders"][key]
    command = {
        "action": "confirm_send",
        "order_id": key,
        "revision": current["revision"],
        "human_confirmed": True,
    }
    assert send(demo, command, source="voice").status_code == 409
    accepted = ok(demo, command)["state"]
    assert accepted["orders"][key]["table_id"] == "1"
    assert all("dragonfruit" not in str(event) for event in accepted["events"])


def test_correction_count_is_distinct_final_diff_not_edit_tap_count(demo):
    key = ok(demo, {"action": "start_order", "table_id": "1"})["result"]["order_id"]
    draft = ok(
        demo,
        {
            "action": "capture_voice",
            "order_id": key,
            "revision": 1,
            "text": "Table 1: one salmon",
        },
        source="voice",
    )["state"]["orders"][key]
    entry = draft["lines"][0]
    for quantity in (2, 3, 1, 2):
        current = snapshot(demo)["orders"][key]
        ok(
            demo,
            {
                "action": "edit_draft",
                "order_id": key,
                "revision": current["revision"],
                "table_id": "1",
                "lines": [
                    {
                        "id": entry["id"],
                        "menu_id": entry["menu_id"],
                        "quantity": quantity,
                    }
                ],
            },
        )
    current = snapshot(demo)["orders"][key]
    result = ok(
        demo,
        {
            "action": "confirm_send",
            "order_id": key,
            "revision": current["revision"],
            "human_confirmed": True,
        },
    )["state"]
    event = next(
        event for event in result["events"] if event["type"] == "order.submitted"
    )
    assert event["payload"]["corrected_draft_lines"] == 1
    assert event["payload"]["initial_voice_draft_line_count"] == 1
    assert "text" not in str(event["payload"])


def test_duplicate_event_and_analytics_failure_do_not_repeat_or_block_operations(demo):
    envelope = body({"action": "start_order", "table_id": "1"})
    first = ok(demo, envelope=envelope)
    pending = demo[2].outbox.pending()
    replay = ok(demo, envelope=envelope)
    assert replay["replayed"] is True
    assert len(replay["state"]["orders"]) == 1
    assert demo[2].outbox.pending() == pending
    changed = {**envelope, "payload": {"action": "start_order", "table_id": "2"}}
    assert send(demo, envelope=changed).status_code == 409
    adapter = FakeAdapter(failures_remaining=1)
    failed = demo[2].outbox.drain(adapter)
    assert failed["last_error"] and failed["pending"] == 1
    key = first["result"]["order_id"]
    ok(
        demo,
        {
            "action": "edit_draft",
            "order_id": key,
            "revision": 1,
            "table_id": "1",
            "lines": [{"id": "one", "menu_id": "salmon", "quantity": 1}],
        },
    )
    final = demo[2].outbox.drain(adapter)
    assert final["pending"] == 0 and final["sent"] == 2
    assert len(adapter.events) == 2


def test_order_beyond_total_physical_capacity_is_rejected_not_waited_forever(demo):
    key = ok(demo, {"action": "start_order", "table_id": "1"})["result"]["order_id"]
    edited = ok(
        demo,
        {
            "action": "edit_draft",
            "order_id": key,
            "revision": 1,
            "table_id": "1",
            "lines": [{"id": "large", "menu_id": "salmon", "quantity": 7}],
        },
    )
    assert (
        send(
            demo,
            {
                "action": "confirm_send",
                "order_id": key,
                "revision": edited["result"]["revision"],
                "human_confirmed": True,
            },
        ).status_code
        == 409
    )
    assert not snapshot(demo)["dishes"]


def test_kitchen_voice_never_selects_first_ambiguous_order_or_unit(demo):
    first = order(demo, quantity=2, table="1")
    second = order(demo, table="1", actor="server-2")
    ambiguous_order = ok(
        demo,
        {"action": "kitchen_voice", "text": "Heard, table 1"},
        actor="cook-1",
        source="voice",
    )
    assert ambiguous_order["result"]["flags"]
    assert snapshot(demo)["orders"][first]["acknowledged_at"] is None
    assert snapshot(demo)["orders"][second]["acknowledged_at"] is None
    ack(demo, first)
    ambiguous_unit = ok(
        demo,
        {"action": "kitchen_voice", "text": "Start table 1 salmon"},
        actor="cook-1",
        source="voice",
    )
    assert ambiguous_unit["result"]["flags"]
    assert all(d["started_at"] is None for d in units(demo, first))


def test_canonical_event_ingress_preserves_id_and_rejects_wrong_target(demo):
    key = order(demo)
    ack(demo, key)
    dish = units(demo, key)[0]
    zone = snapshot(demo)["zones"][dish["zone_id"]]
    canonical = {
        "event_id": str(uuid4()),
        "type": "dish.ready",
        "order_id": key,
        "dish_id": "wrong-unit",
        "source": "camera",
        "actor": "plating-cam",
        "time": "2026-11-14T23:00:00Z",
        "run_id": "canonical-test",
        "simulated": True,
        "payload": {
            "zone_id": zone["id"],
            "assignment_version": zone["assignment_version"],
            "stable_ms": 1600,
        },
    }
    headers = {"X-Demo-Session": demo[1]["cook-1"]}
    assert (
        demo[0].post("/api/v2/events", json=canonical, headers=headers).status_code
        == 409
    )
    assert units(demo, key)[0]["ready_at"] is None
    canonical["dish_id"] = dish["id"]
    response = demo[0].post("/api/v2/events", json=canonical, headers=headers)
    assert response.status_code == 200, response.text
    stored = next(
        event
        for event in response.json()["state"]["events"]
        if event["event_id"] == canonical["event_id"]
    )
    assert stored["type"] == "dish.ready" and stored["time"] == canonical["time"]
    assert stored["run_id"] == "canonical-test" and stored["simulated"]
    assert (
        demo[0]
        .post("/api/v2/events", json=canonical, headers=headers)
        .json()["replayed"]
    )
