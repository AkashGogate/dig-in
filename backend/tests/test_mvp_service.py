"""Two service projections and handoff rules, without hardware/cloud/real TTS.

The summary is recipient/role-scoped; the deliberately global demo state route
is not a confidentiality boundary. Response commands still enforce recipients.
"""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mvp import api
from app.mvp.contracts import Command
from app.mvp.domain import Restaurant


@pytest.fixture
def service(monkeypatch):
    restaurant = Restaurant()
    monkeypatch.setattr(api, "restaurant", restaurant)
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        tokens = {
            key: restaurant.session(key)["session_id"]
            for key in ("server-1", "server-2", "cook-1", "lead-1")
        }
        yield restaurant, client, tokens


def send(service, payload, actor="server-1", source="tap", envelope=None):
    return service[1].post(
        "/api/v2/commands",
        json=envelope
        or Command(
            event_id=str(uuid4()),
            source=source,
            payload=payload,
        ).model_dump(mode="json"),
        headers={"X-Demo-Session": service[2][actor]},
    )


def ok(service, payload, **kwargs):
    response = send(service, payload, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()


def order(service, quantity=1, actor="server-1", table="1", submit=True):
    key = ok(service, {"action": "start_order", "table_id": table}, actor=actor)[
        "result"
    ]["order_id"]
    edited = ok(
        service,
        {
            "action": "edit_draft",
            "order_id": key,
            "revision": 1,
            "table_id": table,
            "lines": [{"id": "dish", "menu_id": "salmon", "quantity": quantity}],
        },
        actor=actor,
    )
    if submit:
        ok(
            service,
            {
                "action": "confirm_send",
                "order_id": key,
                "revision": edited["result"]["revision"],
                "human_confirmed": True,
            },
            actor=actor,
        )
    return key


def summary(service, actor="server-1", audience="server"):
    response = service[1].get(
        "/api/v2/service/summary",
        params={"audience": audience},
        headers={"X-Demo-Session": service[2][actor]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def publish(service, key, kind="delay", note="Check with the pass"):
    return ok(
        service,
        {
            "action": "publish_service_update",
            "order_id": key,
            "kind": kind,
            "note": note,
        },
        actor="cook-1",
    )["result"]["update_id"]


def units(service, key):
    return [d for d in service[0].state.dishes.values() if d.order_id == key]


def ready_one(service, key):
    ok(service, {"action": "acknowledge", "order_id": key}, actor="cook-1")
    dish = units(service, key)[0]
    ok(service, {"action": "ready_dish", "dish_id": dish.id}, actor="cook-1")
    return dish.id


def test_summary_scope_and_read_only_generation(service):
    first = order(service)
    second = order(service, actor="server-2", table="2")
    order(service, submit=False)
    before = service[0].snapshot()
    mine = summary(service)
    assert [o["order_id"] for o in mine["orders"]] == [first]
    assert second not in mine["text"]
    assert mine["counts"]["awaiting_acknowledgment"] == 1
    assert mine["generated_at"] and mine["actor_id"] == "server-1"
    kitchen = summary(service, "cook-1", "kitchen")
    assert {o["order_id"] for o in kitchen["orders"]} == {first, second}
    assert all(d["next_action"] == "acknowledge" for d in kitchen["lineup"])
    assert service[0].snapshot() == before
    assert len(summary(service, "lead-1")["orders"]) == 2


@pytest.mark.parametrize(
    ("actor", "audience"), [("server-1", "kitchen"), ("cook-1", "server")]
)
def test_wrong_audience_is_denied(service, actor, audience):
    response = service[1].get(
        "/api/v2/service/summary",
        params={"audience": audience},
        headers={"X-Demo-Session": service[2][actor]},
    )
    assert response.status_code == 409
    assert service[1].get("/api/v2/service/summary?audience=server").status_code == 409


def test_update_identity_is_derived_from_session_and_order(service):
    key = order(service, actor="server-2")
    envelope = Command(
        event_id=str(uuid4()),
        device_id="untrusted-device-label",
        payload={
            "action": "publish_service_update",
            "order_id": key,
            "kind": "needs_attention",
            "note": "  staff  typed note\n ",
        },
    ).model_dump(mode="json")
    result = ok(service, envelope["payload"], actor="cook-1", envelope=envelope)
    update = next(iter(result["state"]["service_updates"].values()))
    assert update["sender_id"] == "cook-1" and update["recipient_id"] == "server-2"
    assert update["note"] == "staff typed note"
    assert summary(service)["updates"] == []
    assert summary(service, "server-2")["updates"][0]["id"] == update["id"]
    assert "staff typed note" not in str(service[0].outbox.pending())
    # Compatibility limit: global demo snapshots expose authored notes; never
    # describe this route as a private inbox or production authentication.
    assert "staff typed note" in service[1].get("/api/v2/state").text


@pytest.mark.parametrize(
    ("actor", "source"),
    [("server-1", "tap"), ("cook-1", "voice"), ("cook-1", "camera")],
)
def test_only_explicit_kitchen_taps_publish(service, actor, source):
    key = order(service)
    before = service[0].snapshot()
    assert (
        send(
            service,
            {
                "action": "publish_service_update",
                "order_id": key,
                "kind": "delay",
                "note": "typed",
            },
            actor=actor,
            source=source,
        ).status_code
        == 409
    )
    assert service[0].snapshot() == before


def test_draft_unknown_and_terminal_orders_reject_new_updates(service):
    draft = order(service, submit=False)
    for key in [draft, "missing"]:
        assert (
            send(
                service,
                {"action": "publish_service_update", "order_id": key, "kind": "delay"},
                actor="cook-1",
            ).status_code
            == 409
        )
    key = order(service)
    dish = ready_one(service, key)
    ok(service, {"action": "pickup_dish", "dish_id": dish})
    assert (
        send(
            service,
            {"action": "publish_service_update", "order_id": key, "kind": "delay"},
            actor="cook-1",
        ).status_code
        == 409
    )


def test_ack_resolve_revision_recipient_and_retry_guards(service):
    key = order(service)
    update = publish(service, key)
    payload = {
        "action": "acknowledge_service_update",
        "update_id": update,
        "revision": 1,
    }
    assert send(service, payload, actor="server-2").status_code == 409
    assert (
        send(service, {**payload, "action": "resolve_service_update"}).status_code
        == 409
    )
    envelope = Command(event_id=str(uuid4()), payload=payload).model_dump(mode="json")
    accepted = ok(service, payload, envelope=envelope)
    replay = ok(service, payload, envelope=envelope)
    assert replay["replayed"] is True
    assert accepted["state"]["service_updates"][update]["revision"] == 2
    assert send(service, payload).status_code == 409
    assert (
        send(
            service,
            {**payload, "action": "resolve_service_update", "revision": 2},
            actor="server-2",
        ).status_code
        == 409
    )
    resolved = ok(
        service, {**payload, "action": "resolve_service_update", "revision": 2}
    )
    assert resolved["state"]["service_updates"][update]["revision"] == 3
    assert not summary(service)["updates"]
    assert service[0].state.orders[key].acknowledged_at is None
    assert units(service, key)[0].started_at is None
    assert not any(z.dish_id for z in service[0].state.zones.values())
    assert (
        sum(e.type == "service.update_acknowledged" for e in service[0].state.events)
        == 1
    )


def test_partial_pickup_request_becomes_historical_when_plate_is_gone(service):
    key = order(service, quantity=2)
    assert (
        send(
            service,
            {
                "action": "publish_service_update",
                "order_id": key,
                "kind": "pickup_request",
            },
            actor="cook-1",
        ).status_code
        == 409
    )
    dish = ready_one(service, key)
    publish(service, key, "pickup_request", "One plate at pass")
    current = summary(service)
    assert current["counts"]["ready_for_pickup"] == 1
    assert current["orders"][0]["ready"] == 1 and current["orders"][0]["total"] == 2
    assert current["updates"][0]["currently_actionable"] is True
    assert "partial" in current["updates"][0]["actionability_reason"]
    ok(service, {"action": "pickup_dish", "dish_id": dish})
    after = summary(service)
    assert after["counts"]["ready_for_pickup"] == 0
    assert after["orders"][0]["ready"] == 1
    assert after["updates"][0]["currently_actionable"] is False
    assert "No plates are currently ready" in after["text"]
    assert not service[0].state.notifications


def test_summary_retains_unknown_start_and_distinct_same_table_tickets(service):
    first, second = order(service), order(service, actor="server-2")
    ready_one(service, first)
    response = summary(service, "lead-1")
    assert first in response["text"] and second in response["text"]
    ready = next(d for d in response["lineup"] if d["order_id"] == first)
    assert ready["started_at"] is None and ready["elapsed_seconds"] is None
    assert ready["next_action"] == "pickup_dish"
    assert "percent" not in response["text"]


def test_update_and_receipt_roll_back_if_local_enqueue_fails(service, monkeypatch):
    key = order(service)
    before = service[0].snapshot()
    original = service[0].outbox.enqueue

    def fail(events):
        raise ValueError("queue failed")

    monkeypatch.setattr(service[0].outbox, "enqueue", fail)
    envelope = Command(
        event_id=str(uuid4()),
        payload={"action": "publish_service_update", "order_id": key, "kind": "delay"},
    )
    with pytest.raises(ValueError, match="queue failed"):
        service[0].execute(envelope, service[2]["cook-1"])
    assert service[0].snapshot() == before
    assert envelope.event_id not in service[0].receipts
    monkeypatch.setattr(service[0].outbox, "enqueue", original)
    assert service[0].execute(envelope, service[2]["cook-1"])["replayed"] is False


def test_summary_uses_captured_state_even_if_live_state_changes_before_render(
    service, monkeypatch
):
    from app.mvp import domain, service_flow

    first = order(service)

    def render(state, actor, audience, generated_at):
        order(service, table="2")
        return service_flow.build_summary(state, actor, audience, generated_at)

    monkeypatch.setattr(domain, "build_summary", render)
    response = summary(service)
    assert [o["order_id"] for o in response["orders"]] == [first]
    assert len(service[0].state.orders) == 2


def test_service_schemas_discoverable_and_raw_capture_fields_forbidden(service):
    assert "service_summary" in service[1].get("/api/v2/contracts").json()
    key = order(service)
    envelope = {
        "event_id": str(uuid4()),
        "source": "tap",
        "payload": {
            "action": "publish_service_update",
            "order_id": key,
            "kind": "delay",
            "raw_transcript": "not permitted",
        },
    }
    assert send(service, {}, actor="cook-1", envelope=envelope).status_code == 422


def test_acknowledged_waiting_units_can_start_but_cannot_become_ready(service):
    first = order(service, quantity=4)
    waiting = order(service, quantity=4, actor="server-2", table="2")
    ok(service, {"action": "acknowledge", "order_id": first}, actor="cook-1")
    ok(service, {"action": "acknowledge", "order_id": waiting}, actor="cook-1")
    before = summary(service, "cook-1", "kitchen")
    waiting_units = [d for d in before["lineup"] if d["order_id"] == waiting]
    assert len(waiting_units) == 4
    assert all(
        d["zone_id"] is None and d["next_action"] == "start_dish" for d in waiting_units
    )
    key = waiting_units[0]["dish_id"]
    ok(service, {"action": "start_dish", "dish_id": key}, actor="cook-1")
    after = summary(service, "cook-1", "kitchen")
    started = next(d for d in after["lineup"] if d["dish_id"] == key)
    assert started["stage"] == "started" and started["next_action"] == "wait_for_zones"
    assert started["started_at"] is not None
    assert (
        send(
            service, {"action": "ready_dish", "dish_id": key}, actor="cook-1"
        ).status_code
        == 409
    )


def test_lineup_keeps_unit_context_when_current_menu_reuses_ids(service):
    from app.mvp.menu_import import MenuPrepareRequest

    key = ok(service, {"action": "start_order", "table_id": "1"})["result"]["order_id"]
    edited = ok(
        service,
        {
            "action": "edit_draft",
            "order_id": key,
            "revision": 1,
            "table_id": "1",
            "lines": [
                {
                    "id": "guest",
                    "menu_id": "salmon",
                    "quantity": 1,
                    "modifiers": ["no_butter"],
                    "seat": 2,
                    "requests": "Guest asks for separate utensils",
                }
            ],
        },
    )
    ok(
        service,
        {
            "action": "confirm_send",
            "order_id": key,
            "revision": edited["result"]["revision"],
            "human_confirmed": True,
        },
    )
    candidate = service[0].prepare_menu(
        MenuPrepareRequest(
            content='[{"id":"salmon","name":"Unrelated new menu item"}]'
        ),
        service[2]["lead-1"],
    )
    ok(
        service,
        {
            "action": "activate_menu",
            "candidate_id": candidate["candidate_id"],
            "expected_menu_revision": candidate["expected_menu_revision"],
            "human_confirmed": True,
        },
        actor="lead-1",
    )
    unit = summary(service, "cook-1", "kitchen")["lineup"][0]
    assert unit["item_name"] == "Salmon & greens"
    assert unit["modifier_names"] == ["No butter"] and unit["modifiers"] == [
        "no_butter"
    ]
    assert unit["seat"] == 2 and unit["requests"] == "Guest asks for separate utensils"
    assert unit["zone_needs_review"] is False
