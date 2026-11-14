"""Integration checks for staff authority and restaurant invariants.

Use a fresh authoritative restaurant per test; both simulated staff clients share it.
No paid speech service, browser-local state, or physical camera is involved.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.coordination import api
from app.coordination.domain import Restaurant


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setattr(api, "restaurant", Restaurant())
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        sessions = {}
        for actor in ("server-1", "server-2", "cook-1", "lead-1"):
            response = client.post("/api/v1/sessions", json={"actor_id": actor})
            assert response.status_code == 200, response.text
            sessions[actor] = response.json()["session_id"]
        yield client, sessions


def envelope(payload, *, source="manual", kind="command", event_id=None):
    return {
        "id": event_id or str(uuid4()),
        "schema_version": 1,
        "source": source,
        "kind": kind,
        "occurred_at": "2026-11-14T18:00:00Z",
        "device_id": "integration-test",
        "payload": payload,
    }


def post(
    demo, payload, *, actor="server-1", source="manual", kind="command", event_id=None
):
    client, sessions = demo
    return client.post(
        "/api/v1/commands",
        headers={"X-Demo-Session": sessions[actor]},
        json=envelope(payload, source=source, kind=kind, event_id=event_id),
    )


def ok(demo, payload, **kwargs):
    response = post(demo, payload, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()


def state(demo):
    response = demo[0].get("/api/v1/state")
    assert response.status_code == 200, response.text
    return response.json()


def line(line_id="line-1", menu_id="salmon", seat=1, quantity=1, **overrides):
    return dict(id=line_id, menu_id=menu_id, seat=seat, quantity=quantity, **overrides)


def draft(demo, *, actor="server-1", table="1", lines=None):
    result = ok(demo, {"action": "start_order", "table_id": table}, actor=actor)
    order_id = result["result"]["order_id"]
    revision = result["state"]["orders"][order_id]["revision"]
    result = ok(
        demo,
        {
            "action": "edit_draft",
            "order_id": order_id,
            "revision": revision,
            "table_id": table,
            "lines": lines or [line()],
        },
        actor=actor,
    )
    return order_id, result["state"]["orders"][order_id]["revision"]


def submitted(demo, *, actor="server-1", table="1", lines=None):
    order_id, revision = draft(demo, actor=actor, table=table, lines=lines)
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


def acknowledge(demo, order_id, *, source="manual"):
    return ok(
        demo,
        {"action": "acknowledge", "order_id": order_id},
        actor="cook-1",
        source=source,
    )


def advance(demo, dish_id, stage, *, actor="cook-1"):
    return ok(
        demo,
        {"action": "advance_dish", "dish_id": dish_id, "stage": stage},
        actor=actor,
    )


def ready_order(demo):
    order_id = submitted(demo)
    acknowledge(demo, order_id)
    dish_id = next(
        d["id"] for d in state(demo)["dishes"].values() if d["order_id"] == order_id
    )
    for stage in ("preparing", "partially_plated", "plated", "ready"):
        advance(demo, dish_id, stage)
    task_id = next(
        k for k, t in state(demo)["tasks"].items() if dish_id in t["dish_ids"]
    )
    return order_id, dish_id, task_id


def task(demo, task_id, operation, *, actor="server-1", **extra):
    return ok(
        demo,
        {"action": "task_action", "task_id": task_id, "operation": operation, **extra},
        actor=actor,
    )


def test_manual_start_needs_no_positioning_and_table_does_not_drift(demo):
    response = ok(demo, {"action": "start_order", "table_id": "3"})
    order_id = response["result"]["order_id"]
    assert response["state"]["orders"][order_id]["table_id"] == "3"
    assert not response["result"].get("positioning")
    # A positioning adapter has no authority to retarget an existing draft.
    bad = post(
        demo,
        {
            "action": "edit_draft",
            "order_id": order_id,
            "revision": 1,
            "table_id": "1",
            "lines": [line()],
        },
        source="positioning",
    )
    assert bad.status_code != 200
    assert state(demo)["orders"][order_id]["table_id"] == "3"


def test_voice_cannot_submit_and_human_gate_is_required(demo):
    order_id, revision = draft(demo)
    send = {
        "action": "confirm_send",
        "order_id": order_id,
        "revision": revision,
        "human_confirmed": True,
    }
    assert post(demo, send, source="voice").status_code != 200
    assert post(demo, {**send, "human_confirmed": False}).status_code != 200
    assert state(demo)["orders"][order_id]["status"] == "draft"
    accepted = ok(demo, send)
    order = accepted["state"]["orders"][order_id]
    assert order["status"] == "submitted"
    assert order["status_history"] == ["draft", "submitting", "submitted"]
    assert order["acknowledged"] is False


def test_readback_only_proposes_targeted_correction_and_stale_confirmation_fails(demo):
    lines = [
        line(modifiers=["no butter"], requests="nut allergy"),
        line("line-2", "risotto", 2, modifiers=["no cheese"]),
    ]
    order_id, revision = draft(demo, lines=lines)
    compared = ok(
        demo,
        {
            "action": "readback",
            "order_id": order_id,
            "revision": revision,
            "transcript": "seat 1 salmon quantity 2",
        },
        source="voice",
    )
    order = compared["state"]["orders"][order_id]
    assert order["status"] == "draft"
    assert order["lines"][0]["quantity"] == 1
    proposal = order["proposal"]
    assert proposal["line_id"] == "line-1"
    assert proposal["quantity"] == 2
    corrected = ok(
        demo,
        {
            "action": "accept_correction",
            "order_id": order_id,
            "revision": revision,
            "proposal_id": proposal["id"],
        },
    )
    changed = corrected["state"]["orders"][order_id]
    assert changed["revision"] > revision
    assert changed["lines"][0]["quantity"] == 2
    assert changed["lines"][0]["modifiers"] == ["no butter"]
    assert changed["lines"][0]["requests"] == "nut allergy"
    assert changed["lines"][1] == order["lines"][1]
    assert changed["status"] == "draft"
    assert (
        post(
            demo,
            {
                "action": "confirm_send",
                "order_id": order_id,
                "revision": revision,
                "human_confirmed": True,
            },
        ).status_code
        != 200
    )
    assert state(demo)["orders"][order_id]["status"] == "draft"


def test_repeated_dish_readback_requires_seat_or_line_clarification(demo):
    order_id, revision = draft(demo, lines=[line(), line("line-2", seat=2)])
    result = ok(
        demo,
        {
            "action": "readback",
            "order_id": order_id,
            "revision": revision,
            "transcript": "salmon quantity 2",
        },
        source="voice",
    )
    proposal = result["state"]["orders"][order_id]["proposal"]
    assert proposal["question"]
    assert proposal["quantity"] is None
    assert (
        post(
            demo,
            {
                "action": "accept_correction",
                "order_id": order_id,
                "revision": revision,
                "proposal_id": proposal["id"],
            },
        ).status_code
        != 200
    )


def test_retry_is_idempotent_but_reusing_id_for_different_payload_is_rejected(demo):
    command = {"action": "start_order", "table_id": "1"}
    first = ok(demo, command, event_id="stable-start")
    second = ok(demo, command, event_id="stable-start")
    assert first["result"]["order_id"] == second["result"]["order_id"]
    assert len(state(demo)["orders"]) == 1
    collision = post(demo, {**command, "table_id": "2"}, event_id="stable-start")
    assert collision.status_code != 200
    assert len(state(demo)["orders"]) == 1


def test_submission_retry_does_not_duplicate_dishes_tasks_or_recipe_deductions(demo):
    order_id, revision = draft(demo)
    send = {
        "action": "confirm_send",
        "order_id": order_id,
        "revision": revision,
        "human_confirmed": True,
    }
    ok(demo, send, event_id="stable-send")
    ok(demo, send, event_id="stable-send")
    snapshot = state(demo)
    assert len(snapshot["dishes"]) == 1
    assert snapshot["tasks"] == {}
    assert snapshot["computed"]["balances"]["salmon"] == 12
    assert snapshot["computed"]["expected_consumption"]["salmon"] == 1


def test_acknowledgement_partial_plating_ready_pickup_and_served_are_distinct(demo):
    order_id = submitted(demo, lines=[line(quantity=2)])
    snapshot = acknowledge(demo, order_id, source="voice")["state"]
    dishes = [d for d in snapshot["dishes"].values() if d["order_id"] == order_id]
    assert len(dishes) == 2
    assert all(d["stage"] == "queued" for d in dishes)
    first, second = (d["id"] for d in dishes)
    advance(demo, first, "preparing")
    advance(demo, first, "partially_plated")
    assert not state(demo)["tasks"]
    advance(demo, first, "plated")
    advance(demo, first, "ready")
    snapshot = state(demo)
    assert snapshot["dishes"][second]["stage"] == "queued"
    assert snapshot["computed"]["ticket_stages"][order_id] != "ready"
    assert snapshot["dishes"][first]["stage"] == "ready"
    # Explicit served cannot skip pickup just because a dish was marked ready.
    assert (
        post(
            demo, {"action": "advance_dish", "dish_id": first, "stage": "served"}
        ).status_code
        != 200
    )


def test_inventory_observation_is_not_a_deduction_and_cannot_be_accepted_twice(demo):
    observation = ok(
        demo,
        {
            "action": "observe",
            "kind": "ingredient_change",
            "target_id": "salmon",
            "quantity": 1,
        },
        actor="cook-1",
        source="mock_camera",
        kind="observation",
        event_id="camera-1",
    )
    snapshot = observation["state"]
    assert snapshot["computed"]["balances"]["salmon"] == 12
    observation_id = next(iter(snapshot["observations"]))
    movement = {
        "action": "accept_movement",
        "zone_id": "salmon",
        "kind": "consume",
        "quantity": 1,
        "observation_id": observation_id,
        "reason": "one counted portion removed",
    }
    first = ok(demo, movement, actor="cook-1", event_id="movement-1")
    assert first["state"]["computed"]["balances"]["salmon"] == 11
    ok(demo, movement, actor="cook-1", event_id="movement-1")
    assert (
        post(demo, movement, actor="cook-1", event_id="movement-2").status_code != 200
    )
    assert state(demo)["computed"]["balances"]["salmon"] == 11
    returned = ok(
        demo,
        {
            "action": "accept_movement",
            "zone_id": "salmon",
            "kind": "return",
            "quantity": 1,
            "reason": "unused portion returned",
        },
        actor="cook-1",
    )
    assert returned["state"]["computed"]["balances"]["salmon"] == 12
    assert len(returned["state"]["movements"]) == 2


def test_two_tables_same_dish_keep_ticket_identity_and_bay_capacity(demo):
    first = submitted(demo, lines=[line(quantity=6)])
    second = submitted(demo, actor="server-2", table="2")
    snapshot = state(demo)
    assert {d["order_id"] for d in snapshot["dishes"].values()} == {first, second}
    assert all(len(b["dish_ids"]) <= b["capacity"] for b in snapshot["bays"].values())
    waiting = [d for d in snapshot["dishes"].values() if d["order_id"] == second]
    assert len(waiting) == 1
    assert waiting[0]["bay_id"] is None
    bay = snapshot["bays"]["A"]
    denied = post(
        demo,
        {
            "action": "assign_bay",
            "bay_id": "A",
            "assignment_version": bay["assignment_version"],
            "dish_ids": [waiting[0]["id"]],
        },
        actor="cook-1",
    )
    assert denied.status_code != 200
    assert state(demo)["bays"]["A"]["order_id"] == first


def test_old_assignment_observation_cannot_mark_new_bay_ready(demo):
    submitted(demo)
    snapshot = state(demo)
    bay = next(b for b in snapshot["bays"].values() if b["order_id"])
    stale = post(
        demo,
        {
            "action": "observe",
            "kind": "plate_arrival",
            "target_id": bay["id"],
            "assignment_version": bay["assignment_version"] - 1,
            "quantity": 1,
        },
        actor="cook-1",
        source="mock_camera",
        kind="observation",
    )
    assert stale.status_code != 200
    fresh = ok(
        demo,
        {
            "action": "observe",
            "kind": "plate_arrival",
            "target_id": bay["id"],
            "assignment_version": bay["assignment_version"],
            "quantity": 1,
        },
        actor="cook-1",
        source="mock_camera",
        kind="observation",
    )
    assert fresh["state"]["tasks"] == {}
    assert all(d["stage"] != "ready" for d in fresh["state"]["dishes"].values())


def test_atomic_claim_has_one_winner_across_two_servers(demo):
    _, _, task_id = ready_order(demo)
    barrier = Barrier(2)

    def claim(actor):
        barrier.wait(timeout=5)
        return post(
            demo,
            {"action": "task_action", "task_id": task_id, "operation": "claim"},
            actor=actor,
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(claim, ["server-1", "server-2"]))
    assert sorted(responses) == [200, 409]
    assert state(demo)["tasks"][task_id]["owner"] in {"server-1", "server-2"}


def test_additional_helper_blocks_pickup_until_join_then_served_is_explicit(demo):
    _, dish_id, task_id = ready_order(demo)
    task(demo, task_id, "claim")
    task(demo, task_id, "helpers", additional_helpers=1)
    snapshot = state(demo)
    assert len(snapshot["tasks"][task_id]["helper_slots"]) == 1
    assert snapshot["computed"]["task_blockers"][task_id]
    assert (
        post(
            demo, {"action": "advance_dish", "dish_id": dish_id, "stage": "picked_up"}
        ).status_code
        != 200
    )
    task(demo, task_id, "join", actor="server-2")
    assert not state(demo)["computed"]["task_blockers"][task_id]
    picked_up = advance(demo, dish_id, "picked_up", actor="server-1")
    assert picked_up["state"]["dishes"][dish_id]["stage"] == "picked_up"
    assert picked_up["state"]["dishes"][dish_id]["stage"] != "served"
    served = advance(demo, dish_id, "served", actor="server-1")
    assert served["state"]["dishes"][dish_id]["stage"] == "served"


def test_pending_amendment_needs_new_kitchen_acknowledgement(demo):
    order_id = submitted(demo)
    acknowledge(demo, order_id)
    revision = state(demo)["orders"][order_id]["revision"]
    amended = ok(
        demo,
        {
            "action": "amend",
            "order_id": order_id,
            "revision": revision,
            "line_id": "line-1",
            "quantity": 2,
        },
    )
    order = amended["state"]["orders"][order_id]
    assert order["amendments"]
    assert order["amendments"][-1]["acknowledged"] is False
    acknowledged = ok(
        demo,
        {
            "action": "ack_amendment",
            "order_id": order_id,
            "revision": order["revision"],
        },
        actor="cook-1",
    )
    assert (
        acknowledged["state"]["orders"][order_id]["amendments"][-1]["acknowledged"]
        is True
    )


def test_contract_version_and_observation_command_boundary_are_validated(demo):
    client, sessions = demo
    contracts = client.get("/api/v1/contracts")
    assert contracts.status_code == 200
    assert contracts.json()["schema_version"] == 1
    bad = envelope({"action": "start_order", "table_id": "1"})
    bad["schema_version"] = 99
    assert (
        client.post(
            "/api/v1/commands",
            headers={"X-Demo-Session": sessions["server-1"]},
            json=bad,
        ).status_code
        == 422
    )
    assert (
        post(
            demo,
            {"action": "start_order", "table_id": "1"},
            source="mock_camera",
            kind="observation",
        ).status_code
        != 200
    )
    assert not state(demo)["orders"]


def test_commands_require_session_and_reject_actor_spoofing(demo):
    client, _ = demo
    command = envelope({"action": "start_order", "table_id": "1"})
    assert client.post("/api/v1/commands", json=command).status_code != 200
    assert not state(demo)["orders"]
    command["actor_id"] = "lead-1"
    assert (
        client.post(
            "/api/v1/commands",
            headers={"X-Demo-Session": "not-a-session"},
            json=command,
        ).status_code
        != 200
    )
    assert not state(demo)["orders"]


def test_bay_with_live_food_cannot_be_reused_or_released(demo):
    submitted(demo)
    snapshot = state(demo)
    bay = next(b for b in snapshot["bays"].values() if b["order_id"])
    ok(
        demo,
        {
            "action": "observe",
            "kind": "plate_arrival",
            "target_id": bay["id"],
            "assignment_version": bay["assignment_version"],
            "quantity": 1,
        },
        actor="cook-1",
        source="mock_camera",
        kind="observation",
    )
    denied = post(
        demo,
        {
            "action": "release_bay",
            "bay_id": bay["id"],
            "assignment_version": bay["assignment_version"],
            "reason": "attempted early reuse",
        },
        actor="cook-1",
    )
    assert denied.status_code != 200
    after = state(demo)["bays"][bay["id"]]
    assert after["order_id"] == bay["order_id"]
    assert after["assignment_version"] == bay["assignment_version"]


def test_prep_context_does_not_silently_assign_unattributed_camera_removal(demo):
    order_id = submitted(demo)
    assert (
        post(
            demo, {"action": "select_prep", "order_id": order_id}, actor="cook-1"
        ).status_code
        != 200
    )
    acknowledge(demo, order_id)
    selected = ok(demo, {"action": "select_prep", "order_id": order_id}, actor="cook-1")
    assert selected["state"]["active_prep"]["cook-1"] == order_id
    observation = ok(
        demo,
        {
            "action": "observe",
            "kind": "ingredient_change",
            "target_id": "greens",
            "quantity": 1,
        },
        actor="cook-1",
        source="mock_camera",
        kind="observation",
    )
    observation_id = observation["result"]["observation_id"]
    assert observation["state"]["observations"][observation_id]["order_id"] is None
    attributed = ok(
        demo,
        {
            "action": "observe",
            "kind": "ingredient_change",
            "target_id": "greens",
            "quantity": 1,
            "order_id": order_id,
        },
        actor="cook-1",
        source="mock_camera",
        kind="observation",
    )
    assert (
        attributed["state"]["observations"][attributed["result"]["observation_id"]][
            "order_id"
        ]
        == order_id
    )
    assert attributed["state"]["computed"]["balances"]["greens"] == 20


def test_plate_return_is_distinct_and_requires_manual_bay_reconciliation(demo):
    _, dish_id, task_id = ready_order(demo)
    task(demo, task_id, "claim")
    snapshot = advance(demo, dish_id, "picked_up", actor="server-1")["state"]
    bay_id = snapshot["dishes"][dish_id]["bay_id"]
    bay = snapshot["bays"][bay_id]
    returned = ok(
        demo,
        {
            "action": "observe",
            "kind": "plate_return",
            "target_id": bay_id,
            "assignment_version": bay["assignment_version"],
            "quantity": 1,
        },
        source="mock_camera",
        kind="observation",
    )
    assert returned["state"]["bays"][bay_id]["unresolved_pickup"] is True
    assert len(returned["state"]["orders"]) == 1
    assert returned["state"]["movements"] == []
    release = {
        "action": "release_bay",
        "bay_id": bay_id,
        "assignment_version": bay["assignment_version"],
        "reason": "clear delivered batch",
    }
    assert post(demo, release, actor="cook-1").status_code != 200
    reconcile = {
        "action": "reconcile_bay",
        "bay_id": bay_id,
        "assignment_version": bay["assignment_version"],
        "occupied": False,
        "reason": "staff checked returned plate and cleared bay",
    }
    assert post(demo, reconcile, actor="cook-1", source="voice").status_code != 200
    reconciled = ok(demo, reconcile, actor="cook-1")
    assert reconciled["state"]["bays"][bay_id]["unresolved_pickup"] is False
    released = ok(demo, release, actor="cook-1")
    assert released["state"]["bays"][bay_id]["order_id"] is None
    assert released["state"]["dishes"][dish_id]["stage"] == "picked_up"


@pytest.mark.parametrize(
    "enabled,convention,dish_count,observed_count,expected_ready",
    [
        (False, "complete_batches_only", 1, 1, False),
        (True, "staging", 1, 1, False),
        (True, "complete_batches_only", 2, 2, False),
        (True, "complete_batches_only", 1, 2, False),
        (True, "complete_batches_only", 1, None, False),
        (True, "complete_batches_only", 1, 1, True),
    ],
)
def test_conditional_auto_ready_requires_explicit_convention_and_single_plate(
    demo, enabled, convention, dish_count, observed_count, expected_ready
):
    # Configure only the experimental feature, otherwise run real staff/API paths.
    api.restaurant.state.auto_ready_enabled = enabled
    order_id = submitted(demo, lines=[line(quantity=dish_count)])
    acknowledge(demo, order_id)
    snapshot = state(demo)
    dish_ids = [
        d["id"] for d in snapshot["dishes"].values() if d["order_id"] == order_id
    ]
    bay_id = snapshot["dishes"][dish_ids[0]]["bay_id"]
    api.restaurant.state.bays[bay_id].convention = convention
    for dish_id in dish_ids:
        advance(demo, dish_id, "preparing")
    bay = state(demo)["bays"][bay_id]
    arrived = ok(
        demo,
        {
            "action": "observe",
            "kind": "plate_arrival",
            "target_id": bay_id,
            "assignment_version": bay["assignment_version"],
            "quantity": observed_count,
        },
        actor="cook-1",
        source="mock_camera",
        kind="observation",
    )
    ready = all(arrived["state"]["dishes"][d]["stage"] == "ready" for d in dish_ids)
    assert ready is expected_ready
    assert bool(arrived["state"]["tasks"]) is expected_ready


def test_available_queue_filters_before_top_three_and_explains_aging_and_override(demo):
    from datetime import datetime, timedelta

    ids = []
    for table in ("1", "3", "2", "3"):
        created = ok(
            demo,
            {
                "action": "create_task",
                "table_id": table,
                "type": "guest_request",
                "reason": "water refill",
            },
        )
        ids.append(created["result"]["task_id"])
    ranked = state(demo)["computed"]["ranked_tasks"]
    assert len(ranked) == 3
    assert all(t["priority_reason"] for t in ranked)
    patio = (
        demo[0].get("/api/v1/state?section=patio").json()["computed"]["ranked_tasks"]
    )
    assert len(patio) == 2
    assert all(t["section"] == "patio" for t in patio)
    _, _, run_id = ready_order(demo)
    assert state(demo)["computed"]["ranked_tasks"][0]["id"] == run_id
    # An aging request eventually outranks freshly ready food, avoiding starvation.
    api.restaurant.state.tasks[ids[-1]].created_at = (
        datetime.now(UTC) - timedelta(minutes=10)
    ).isoformat()
    assert state(demo)["computed"]["ranked_tasks"][0]["id"] == ids[-1]
    task(demo, ids[0], "urgent", actor="lead-1", reason="guest needs urgent assistance")
    top = state(demo)["computed"]["ranked_tasks"][0]
    assert top["id"] == ids[0]
    assert "Shift lead" in top["priority_reason"]
    assert "urgent assistance" in top["priority_reason"]


def test_one_arrival_does_not_attribute_two_preparing_dishes(demo):
    order_id = submitted(demo, lines=[line(quantity=2)])
    snapshot = acknowledge(demo, order_id)["state"]
    dishes = [d for d in snapshot["dishes"].values() if d["order_id"] == order_id]
    for dish in dishes:
        advance(demo, dish["id"], "preparing")
    bay = snapshot["bays"][dishes[0]["bay_id"]]
    observed = ok(
        demo,
        {
            "action": "observe",
            "kind": "plate_arrival",
            "target_id": bay["id"],
            "assignment_version": bay["assignment_version"],
            "quantity": 1,
        },
        actor="cook-1",
        source="mock_camera",
        kind="observation",
    )
    assert observed["result"]["disposition"] == "clarify_staged_dish"
    assert all(
        observed["state"]["dishes"][d["id"]]["stage"] == "preparing" for d in dishes
    )
    assert not observed["state"]["tasks"]
