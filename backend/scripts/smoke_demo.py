"""Credential-free API smoke; runs against a started shared backend.

uv run python -m scripts.smoke_demo [--base-url http://localhost:8000]
Adds uniquely prefixed demo records; never resets other collaborators' state.
"""

from __future__ import annotations

import argparse
import time
from uuid import uuid4

import httpx

from app.coordination.contracts import Command, Line


def run(base_url: str):
    with httpx.Client(base_url=base_url, timeout=10) as client:
        sessions = {}
        for actor in ("server-1", "server-2", "cook-1"):
            response = client.post("/api/v1/sessions", json={"actor_id": actor})
            response.raise_for_status()
            sessions[actor] = response.json()["session_id"]

        def send(payload, actor="server-1", source="manual", command=None):
            body = command or Command(
                id=str(uuid4()),
                source=source,
                kind="observation" if payload["action"] == "observe" else "command",
                device_id="smoke-demo",
                payload=payload,
            ).model_dump(mode="json")
            response = client.post(
                "/api/v1/commands",
                json=body,
                headers={"X-Demo-Session": sessions[actor]},
            )
            assert response.is_success, response.text
            return response.json(), body

        def order(table, lines, actor="server-1", readback=False):
            data, _ = send({"action": "start_order", "table_id": table}, actor)
            key = data["result"]["order_id"]
            data, _ = send(
                {
                    "action": "edit_draft",
                    "order_id": key,
                    "revision": 1,
                    "table_id": table,
                    "lines": lines,
                },
                actor,
            )
            revision = data["state"]["orders"][key]["revision"]
            if readback:
                data, _ = send(
                    {
                        "action": "readback",
                        "order_id": key,
                        "revision": revision,
                        "transcript": "seat 1 salmon quantity 2",
                    },
                    actor,
                    "voice",
                )
                proposal = data["result"]["proposal"]
                data, _ = send(
                    {
                        "action": "accept_correction",
                        "order_id": key,
                        "revision": revision,
                        "proposal_id": proposal["id"],
                    },
                    actor,
                )
                revision = data["result"]["revision"]
            data, body = send(
                {
                    "action": "confirm_send",
                    "order_id": key,
                    "revision": revision,
                    "human_confirmed": True,
                },
                actor,
            )
            again, _ = send(body["payload"], actor, command=body)
            assert again["replayed"]
            assert again["state"]["orders"][key]["status"] == "submitted"
            send({"action": "acknowledge", "order_id": key}, "cook-1", "voice")
            return key

        first = order(
            "1",
            [
                Line(
                    id="salmon-line",
                    seat=1,
                    menu_id="salmon",
                    quantity=1,
                    modifiers=["no butter"],
                    requests="explicit dairy request",
                ).model_dump(),
                Line(
                    id="risotto-line", seat=2, menu_id="risotto", quantity=1
                ).model_dump(),
            ],
            readback=True,
        )
        second = order(
            "2",
            [Line(id="same-salmon", seat=1, menu_id="salmon", quantity=1).model_dump()],
            "server-2",
        )
        send({"action": "select_prep", "order_id": first}, "cook-1")
        data, _ = send(
            {
                "action": "observe",
                "kind": "ingredient_change",
                "target_id": "salmon",
                "quantity": 1,
                "order_id": first,
            },
            "cook-1",
            "mock_camera",
        )
        before = data["state"]["computed"]["balances"]["salmon"]
        data, body = send(
            {
                "action": "accept_movement",
                "zone_id": "salmon",
                "kind": "consume",
                "quantity": 1,
                "observation_id": data["result"]["observation_id"],
                "order_id": first,
                "reason": "Counted portion demo",
            },
            "cook-1",
        )
        data, _ = send(body["payload"], "cook-1", command=body)
        assert data["state"]["computed"]["balances"]["salmon"] == before - 1
        data, _ = send(
            {
                "action": "accept_movement",
                "zone_id": "salmon",
                "kind": "return",
                "quantity": 1,
                "reason": "Unused portion returned",
            },
            "cook-1",
        )
        assert data["state"]["computed"]["balances"]["salmon"] == before
        dishes = [
            d for d in data["state"]["dishes"].values() if d["order_id"] == second
        ]
        dish = dishes[0]
        assert dish["bay_id"], (
            "Demo bays are full; restart a private demo backend or finish existing runs first"
        )
        bay = data["state"]["bays"][dish["bay_id"]]
        send(
            {"action": "advance_dish", "dish_id": dish["id"], "stage": "preparing"},
            "cook-1",
        )
        data, _ = send(
            {
                "action": "observe",
                "kind": "plate_arrival",
                "target_id": bay["id"],
                "assignment_version": bay["assignment_version"],
                "quantity": 1,
            },
            "cook-1",
            "mock_camera",
        )
        assert data["state"]["dishes"][dish["id"]]["stage"] == "partially_plated"
        for stage in ("plated", "ready"):
            data, _ = send(
                {"action": "advance_dish", "dish_id": dish["id"], "stage": stage},
                "cook-1",
            )
        ready_at = time.monotonic()
        task = next(
            t for t in data["state"]["tasks"].values() if dish["id"] in t["dish_ids"]
        )
        send({"action": "task_action", "task_id": task["id"], "operation": "claim"})
        send(
            {
                "action": "task_action",
                "task_id": task["id"],
                "operation": "helpers",
                "additional_helpers": 1,
            }
        )
        data, _ = send(
            {"action": "task_action", "task_id": task["id"], "operation": "join"},
            "server-2",
        )
        assert not data["state"]["computed"]["task_blockers"][task["id"]]
        data, _ = send(
            {
                "action": "observe",
                "kind": "plate_removal",
                "target_id": bay["id"],
                "assignment_version": bay["assignment_version"],
                "quantity": 1,
            },
            "cook-1",
            "mock_camera",
        )
        assert data["state"]["dishes"][dish["id"]]["stage"] == "picked_up"
        pickup_delay = time.monotonic() - ready_at
        data, _ = send(
            {"action": "advance_dish", "dish_id": dish["id"], "stage": "served"}
        )
        assert data["state"]["tasks"][task["id"]]["status"] == "completed"
        assert all(
            d["stage"] == "queued"
            for d in data["state"]["dishes"].values()
            if d["order_id"] == first
        )
        send(
            {
                "action": "observe",
                "kind": "plate_return",
                "target_id": bay["id"],
                "assignment_version": bay["assignment_version"],
            },
            "cook-1",
            "mock_camera",
        )
        send(
            {
                "action": "reconcile_bay",
                "bay_id": bay["id"],
                "assignment_version": bay["assignment_version"],
                "occupied": False,
                "reason": "Returned empty plate cleared by staff",
            },
            "cook-1",
        )
        send(
            {
                "action": "release_bay",
                "bay_id": bay["id"],
                "assignment_version": bay["assignment_version"],
                "reason": "Empty and delivered",
            },
            "cook-1",
        )
        print(
            f"PASS mock smoke: 2 tables/tickets, reviewed correction, retry-safe send/stock, partial vs ready, helper slot, pickup + explicit served + return. Ready-to-pickup {pickup_delay:.3f}s (synthetic API timing, not staff benchmark)."
        )
        print(
            "Mock assertions: duplicate effects 0; wrong-ticket transitions 0; false-ready at partial 0; net stock error after return 0. Noise/CV/prompt burden and physical timing unmeasured."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    run(parser.parse_args().base_url)
