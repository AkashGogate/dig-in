"""MVP HTTP smoke: use a fresh running backend; never resets another session."""

from __future__ import annotations

import argparse
from uuid import uuid4

import httpx

from app.mvp.contracts import Command


def run(base_url):
    with httpx.Client(base_url=base_url, timeout=10) as client:
        sessions = {}
        for actor in ("server-1", "cook-1"):
            response = client.post("/api/v2/sessions", json={"actor_id": actor})
            response.raise_for_status()
            sessions[actor] = response.json()["session_id"]

        def send(payload, actor="server-1", source="tap", body=None):
            body = body or Command(
                event_id=str(uuid4()),
                source=source,
                run_id="mvp-http-smoke",
                simulated=True,
                payload=payload,
            ).model_dump(mode="json")
            response = client.post(
                "/api/v2/commands",
                json=body,
                headers={"X-Demo-Session": sessions[actor]},
            )
            assert response.is_success, response.text
            return response.json(), body

        menu = client.get("/api/v2/menu").json()
        data, _ = send({"action": "start_order", "table_id": "1"})
        key = data["result"]["order_id"]
        lines = [
            {"id": str(n), "menu_id": item["id"], "quantity": 1}
            for n, item in enumerate(menu["items"][:2])
        ]
        assert len(lines) == 2, "Load a two-dish demo menu"
        data, _ = send(
            {
                "action": "edit_draft",
                "order_id": key,
                "revision": 1,
                "table_id": "1",
                "lines": lines,
            }
        )
        data, body = send(
            {
                "action": "confirm_send",
                "order_id": key,
                "revision": data["result"]["revision"],
                "human_confirmed": True,
            }
        )
        replay, _ = send(body["payload"], body=body)
        assert replay["replayed"]
        data, _ = send({"action": "acknowledge", "order_id": key}, "cook-1")
        dishes = [d for d in data["state"]["dishes"].values() if d["order_id"] == key]
        assert len({d["zone_id"] for d in dishes}) == 2 and all(
            d["zone_id"] for d in dishes
        ), "Fresh backend needs two free zones"
        first, second = dishes
        zone = data["state"]["zones"][first["zone_id"]]
        data, _ = send(
            {
                "action": "zone_observation",
                "zone_id": zone["id"],
                "assignment_version": zone["assignment_version"],
                "occupied": True,
                "stable_ms": 1600,
            },
            "cook-1",
            "camera",
        )
        assert data["state"]["computed"]["order_progress"][key]["ready"] == 1
        assert not data["state"]["orders"][key]["ready_notified"]
        send(
            {
                "action": "camera_status",
                "camera_id": zone["camera_id"],
                "status": "blocked",
                "reason": "Scripted fallback test",
            },
            "cook-1",
            "system",
        )
        data, _ = send(
            {
                "action": "ready_dish",
                "dish_id": second["id"],
                "fallback_reason": "camera blocked",
            },
            "cook-1",
        )
        assert data["state"]["orders"][key]["ready_notified"]
        for dish in dishes:
            data, _ = send(
                {
                    "action": "pickup_dish",
                    "dish_id": dish["id"],
                    "fallback_reason": "camera blocked",
                }
            )
        data, _ = send({"action": "deliver_order", "order_id": key})
        assert data["state"]["orders"][key]["status"] == "delivered"
        assert (
            len([n for n in data["state"]["notifications"] if n["order_id"] == key])
            == 1
        )
        assert all(
            data["state"]["dishes"][d["id"]]["started_at"] is None for d in dishes
        )
        print(
            "PASS MVP HTTP smoke: two menu dishes, retry-safe send, atomic zones, partial readiness, blocked camera + taps, one all-ready notification, pickup/release and delivered. Start times remain unknown. All data simulated."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    run(parser.parse_args().base_url)
