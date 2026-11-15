"""Full application composition: auth, mutable menu, voice, CV and both roles.

The deployed ASGI app is used, not a second test-only router assembly. Provider
and image evidence stay simulated; this verifies wiring rather than STT/CV quality.
"""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.mvp import api
from app.mvp.contracts import Command
from app.mvp.domain import Restaurant


@pytest.fixture
def application(monkeypatch):
    from app import server
    from app.log_store import make_session_factory

    monkeypatch.delenv("DIG_IN_MENU_PATH", raising=False)
    monkeypatch.delenv("DIG_IN_REQUIRE_DIETARY_CHECK", raising=False)
    monkeypatch.setenv("DIG_IN_VOICE_LIVE", "0")
    monkeypatch.setenv("DEMO_AUTH_USER", "demo")
    monkeypatch.setenv("DEMO_AUTH_PASS", "test-only")
    core = Restaurant()
    monkeypatch.setattr(api, "restaurant", core)
    engine, factory = make_session_factory("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(server, "engine", engine)
    monkeypatch.setattr(server, "SessionFactory", factory)
    with TestClient(server.app) as client:
        assert client.get("/api/v2/state").status_code == 401
        assert client.get("/healthz").json() == {"status": "ok", "schema_version": 2}
        client.auth = ("demo", "test-only")
        tokens = {}
        for actor in ("server-1", "server-2", "cook-1", "lead-1"):
            response = client.post("/api/v2/sessions", json={"actor_id": actor})
            assert response.status_code == 200
            tokens[actor] = response.json()["session_id"]
        yield client, tokens


def test_uploaded_menu_voice_cv_and_role_handoff_share_one_core(application):
    client, tokens = application

    def command(payload, actor="server-1", source="tap"):
        response = client.post(
            "/api/v2/commands",
            headers={"X-Demo-Session": tokens[actor]},
            json=Command(
                event_id=str(uuid4()),
                source=source,
                payload=payload,
                simulated=True,
                run_id="application-integration",
            ).model_dump(mode="json"),
        )
        assert response.status_code == 200, response.text
        return response.json()

    old = command({"action": "start_order", "table_id": "1"})["result"]["order_id"]
    old_revision = client.get("/api/v2/state").json()["menu_revision"]
    candidate = client.post(
        "/api/v2/menu/prepare",
        headers={"X-Demo-Session": tokens["lead-1"]},
        json={
            "content": json.dumps(
                {
                    "name": "Runtime cafe",
                    "items": [
                        {"id": "noodle", "name": "Noodle bowl", "aliases": ["noodles"]}
                    ],
                }
            )
        },
    )
    assert candidate.status_code == 200, candidate.text
    prepared = candidate.json()
    command(
        {
            "action": "activate_menu",
            "candidate_id": prepared["candidate_id"],
            "expected_menu_revision": prepared["expected_menu_revision"],
            "human_confirmed": True,
        },
        "lead-1",
    )
    order_id = command({"action": "start_order", "table_id": "2"})["result"]["order_id"]
    drafted = command(
        {
            "action": "capture_voice",
            "order_id": order_id,
            "revision": 1,
            "text": "table two one noodle bowl",
        },
        source="voice",
    )
    order = drafted["state"]["orders"][order_id]
    assert order["status"] == "draft" and order["lines"][0]["menu_id"] == "noodle"
    assert drafted["state"]["orders"][old]["menu_revision"] == old_revision
    command(
        {
            "action": "confirm_send",
            "order_id": order_id,
            "revision": order["revision"],
            "human_confirmed": True,
        }
    )
    command({"action": "acknowledge", "order_id": order_id}, "cook-1")
    assert (
        client.get(
            "/api/v2/cv/context", headers={"X-Demo-Session": tokens["server-1"]}
        ).status_code
        == 409
    )
    context = client.get(
        "/api/v2/cv/context", headers={"X-Demo-Session": tokens["cook-1"]}
    ).json()
    zone = next(z for z in context["zones"].values() if z["order_id"] == order_id)
    envelope = {
        "event": {
            "event_id": str(uuid4()),
            "type": "BAY_STATE",
            "source": "cv.plating",
            "camera_id": "plating_cam",
            "observed_at": datetime.now(UTC).isoformat(),
            "bay_id": zone["zone_id"],
            "attribution": {"ticket_id": order_id, "method": "bay_assignment"},
            "payload": {
                "plate_count": 1,
                "occupied": True,
                "assigned_ticket_id": order_id,
                "assigned_table": "2",
                "assigned_course": None,
            },
        },
        "binding": {
            k: zone[k] for k in ("zone_id", "assignment_version", "order_id", "dish_id")
        },
        "evidence": {"stable_ms": 1600, "hand_present": False},
        "simulated": True,
        "run_id": "application-integration",
    }
    observed = client.post(
        "/api/v2/cv/observations",
        headers={"X-Demo-Session": tokens["cook-1"]},
        json=envelope,
    )
    assert observed.status_code == 200, observed.text
    assert client.post(
        "/api/v2/cv/observations",
        headers={"X-Demo-Session": tokens["cook-1"]},
        json=envelope,
    ).json()["replayed"]
    state = client.get("/api/v2/state").json()
    assert state["orders"][order_id]["status"] == "ready"
    assert state["dishes"][zone["dish_id"]]["started_at"] is None
    command(
        {
            "action": "publish_service_update",
            "order_id": order_id,
            "kind": "pickup_request",
            "note": "Ready at pass",
        },
        "cook-1",
    )

    def summary(actor):
        response = client.get(
            "/api/v2/service/summary",
            params={"audience": "server"},
            headers={"X-Demo-Session": tokens[actor]},
        )
        assert response.status_code == 200
        return response.json()

    assert not summary("server-2")["updates"]
    inbox = summary("server-1")
    assert len(inbox["updates"]) == 1
    before = client.get("/api/v2/state").json()["events"]
    summary("server-1")
    assert client.get("/api/v2/state").json()["events"] == before
    command({"action": "pickup_dish", "dish_id": zone["dish_id"]})
    assert summary("server-1")["updates"][0]["currently_actionable"] is False


def test_legacy_binary_cannot_bypass_v2_provider_guards(application, monkeypatch):
    client, _ = application
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-not-a-provider-key")
    session = client.post("/session/start").json()["session_id"]
    with client.websocket_connect(f"/ws/{session}") as ws:
        ws.send_bytes(b"unbounded legacy input")
        assert "disabled" in ws.receive_json()["error"]
