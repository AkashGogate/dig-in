"""Mutable menu/encoding integration: no paid requests or OCR claims."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analytics.outbox import FakeAdapter
from app.mvp import api
from app.mvp.contracts import Command
from app.mvp.domain import Restaurant
from app.mvp.menu import load_menu
from app.mvp.menu_embeddings import EmbeddingError, LocalEmbeddings, OpenAIEmbeddings
from app.mvp.menu_import import MenuPrepareRequest, parse_menu


@pytest.fixture
def runtime(monkeypatch):
    restaurant = Restaurant(embedding_provider=LocalEmbeddings())
    monkeypatch.setattr(api, "restaurant", restaurant)
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        tokens = {
            actor: restaurant.session(actor)["session_id"]
            for actor in ("server-1", "lead-1", "cook-1")
        }
        yield restaurant, client, tokens


def post(runtime, path, data, actor="lead-1"):
    _, client, tokens = runtime
    return client.post(
        f"/api/v2/{path}", json=data, headers={"X-Demo-Session": tokens[actor]}
    )


def command(runtime, payload, actor="lead-1", source="tap", envelope=None):
    return post(
        runtime,
        "commands",
        envelope
        or Command(event_id=str(uuid4()), source=source, payload=payload).model_dump(
            mode="json"
        ),
        actor,
    )


def prepare(runtime, items=None):
    response = post(
        runtime,
        "menu/prepare",
        {
            "content": json.dumps(
                {
                    "id": "new-menu",
                    "name": "Cafe",
                    "items": items
                    or [
                        {
                            "id": "soup",
                            "name": "Tomato soup",
                            "description": "Roasted tomato and basil",
                        }
                    ],
                }
            )
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def activate(runtime, prepared, **changes):
    return command(
        runtime,
        {
            "action": "activate_menu",
            "candidate_id": prepared["candidate_id"],
            "expected_menu_revision": prepared["expected_menu_revision"],
            "human_confirmed": True,
            **changes,
        },
    )


def start(runtime, table="1"):
    response = command(
        runtime, {"action": "start_order", "table_id": table}, "server-1"
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]["order_id"]


def edit(runtime, key, menu_id="salmon", quantity=1, modifiers=None):
    order = runtime[0].state.orders[key]
    response = command(
        runtime,
        {
            "action": "edit_draft",
            "order_id": key,
            "revision": order.revision,
            "table_id": order.table_id,
            "lines": [
                {
                    "id": "line",
                    "menu_id": menu_id,
                    "quantity": quantity,
                    "modifiers": modifiers or [],
                }
            ],
        },
        "server-1",
    )
    assert response.status_code == 200, response.text


def submit(runtime, key):
    order = runtime[0].state.orders[key]
    response = command(
        runtime,
        {
            "action": "confirm_send",
            "order_id": key,
            "revision": order.revision,
            "human_confirmed": True,
        },
        "server-1",
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    ("media_type", "content"),
    [
        ("application/json", '["Tomato soup", {"name":"Basil pasta"}]'),
        (
            "text/csv",
            "name,description,price_cents,aliases\nTomato soup,Roasted tomatoes,900,soup;tomato\nBasil pasta,Fresh basil,,pasta",
        ),
        ("text/plain", "Tomato soup | Roasted tomatoes\nBasil pasta | Fresh basil"),
    ],
)
def test_random_structured_menus_encode_without_dish_specific_changes(
    runtime, media_type, content
):
    before = runtime[0].snapshot()
    response = post(
        runtime,
        "menu/prepare",
        {"media_type": media_type, "content": content, "name": "Random cafe"},
    )
    assert response.status_code == 200, response.text
    candidate = response.json()
    assert candidate["requires_human_review"]
    assert candidate["index"]["item_count"] == 2
    assert candidate["index"]["dimensions"] == 512
    assert candidate["index"]["semantic"] is False
    assert candidate["menu"]["items"][0]["station"] is None
    assert candidate["menu"]["items"][0]["recipe"] is None
    assert candidate["menu"]["items"][0]["typical_minutes"] is None
    assert runtime[0].snapshot() == before
    assert activate(runtime, candidate).status_code == 200
    assert runtime[1].get("/api/v2/menu").json()["name"] == "Random cafe"
    matches = post(
        runtime, "menu/search", {"text": "roasted tomato", "limit": 1}
    ).json()
    assert matches["candidates"][0]["menu_id"] == candidate["menu"]["items"][0]["id"]
    repeated = parse_menu(
        MenuPrepareRequest(content=content, media_type=media_type, name="Random cafe")
    )
    assert repeated.items[0].id == candidate["menu"]["items"][0]["id"]


@pytest.mark.parametrize(
    "content",
    [
        "{broken",
        '{"items": []}',
        '{"name":12,"items":["Soup"]}',
        '[{"name":"---"}]',
        '[{"name":"   "}]',
        '[{"name":"Soup"},{"name":"Soup"}]',
        '[{"name":"Soup","id":"same"},{"name":"Salad","id":"same"}]',
        '[{"name":"Soup","typical_minutes":NaN}]',
        '[{"name":"Soup","invented":true}]',
        '[{"name":"Soup","modifiers":[{"id":"x","name":"A"},{"id":"x","name":"B"}]}]',
    ],
)
def test_invalid_menu_does_not_mutate_active_state(runtime, content):
    before = runtime[0].snapshot()
    response = post(runtime, "menu/prepare", {"content": content})
    assert response.status_code == 422
    assert runtime[0].snapshot() == before


def test_activation_requires_lead_review_current_revision_and_exact_retry(runtime):
    prepared = prepare(runtime)
    assert activate(runtime, prepared, human_confirmed=False).status_code == 409
    payload = {
        "action": "activate_menu",
        "candidate_id": prepared["candidate_id"],
        "expected_menu_revision": prepared["expected_menu_revision"],
        "human_confirmed": True,
    }
    assert command(runtime, payload, "server-1").status_code == 409
    assert command(runtime, payload, source="voice").status_code == 409
    stale = prepare(runtime, [{"id": "pasta", "name": "Pasta"}])
    envelope = Command(event_id=str(uuid4()), payload=payload).model_dump(mode="json")
    accepted = command(runtime, payload, envelope=envelope)
    assert accepted.status_code == 200
    replayed = command(runtime, payload, envelope=envelope).json()
    assert replayed["replayed"] is True
    assert sum(e.type == "menu.activated" for e in runtime[0].state.events) == 1
    assert activate(runtime, stale).status_code == 409
    assert len(runtime[0].outbox.pending()) == 1
    adapter = FakeAdapter()
    runtime[0].outbox.drain(adapter)
    assert len(adapter.events) == 1
    assert (
        next(iter(adapter.events.values()))["payload"]["menu_revision"]
        == prepared["menu_revision"]
    )


def test_unauthorized_preparation_and_search_cannot_trigger_provider(runtime):
    for path, data in [
        ("menu/prepare", {"content": '["Soup"]'}),
        ("menu/search", {"text": "Soup"}),
    ]:
        assert runtime[1].post(f"/api/v2/{path}", json=data).status_code == 409
    assert (
        post(runtime, "menu/prepare", {"content": '["Soup"]'}, "server-1").status_code
        == 409
    )


def test_drafts_and_kitchen_speech_keep_original_menu_after_replacement(runtime):
    key = start(runtime)
    old_revision = runtime[0].state.orders[key].menu_revision
    edit(runtime, key, modifiers=["no_butter"])
    prepared = prepare(
        runtime,
        [
            {
                "id": "salmon",
                "name": "Completely different dish",
                "modifiers": [{"id": "no_butter", "name": "Different modifier"}],
            }
        ],
    )
    assert activate(runtime, prepared).status_code == 200
    # Even an edit after activation uses the draft's pinned original menu.
    edit(runtime, key, modifiers=["no_butter"])
    result = submit(runtime, key)
    assert result["state"]["orders"][key]["lines"][0]["item_name"] == "Salmon & greens"
    dish = next(iter(result["state"]["dishes"].values()))
    assert dish["modifier_names"] == ["No butter"] and dish["typical_minutes"] == 8
    assert runtime[0].state.orders[key].menu_revision == old_revision
    assert (
        command(
            runtime,
            {"action": "kitchen_voice", "text": "Heard table 1"},
            "cook-1",
            "voice",
        ).status_code
        == 200
    )
    started = command(
        runtime,
        {"action": "kitchen_voice", "text": "Start table 1 salmon"},
        "cook-1",
        "voice",
    ).json()
    assert started["state"]["dishes"][dish["id"]]["stage"] == "started"
    new_key = start(runtime, "2")
    edit(runtime, new_key)
    assert (
        runtime[0].state.orders[new_key].lines[0].item_name
        == "Completely different dish"
    )


def test_vector_candidates_never_select_a_dish_or_clear_voice_flags(runtime):
    prepared = prepare(runtime)
    assert activate(runtime, prepared).status_code == 200
    key = start(runtime)
    response = command(
        runtime,
        {
            "action": "capture_voice",
            "order_id": key,
            "revision": 1,
            "text": "Table 1: one roasted tomato and basil",
        },
        "server-1",
        "voice",
    )
    assert response.status_code == 200, response.text
    order = runtime[0].state.orders[key]
    assert not order.lines
    assert any(flag.candidates == ["soup"] for flag in order.flags)
    assert (
        command(
            runtime,
            {
                "action": "confirm_send",
                "order_id": key,
                "revision": order.revision,
                "human_confirmed": True,
            },
            "server-1",
        ).status_code
        == 409
    )
    assert all("roasted tomato" not in str(e.payload) for e in runtime[0].state.events)


def test_old_recipe_expectation_and_balances_survive_menu_replacement(runtime):
    key = start(runtime)
    edit(runtime, key, quantity=2)
    submit(runtime, key)
    before = runtime[0].snapshot()["computed"]
    assert before["expected_consumption"]["salmon"] == 2
    assert activate(runtime, prepare(runtime)).status_code == 200
    after = runtime[0].snapshot()["computed"]
    assert after["expected_consumption"] == before["expected_consumption"]
    assert after["balances"] == before["balances"]
    assert runtime[0].state.stock_movements == []


@pytest.mark.parametrize(
    "vectors", [[[0.0, 0.0]], [[float("nan"), 1.0]], [], [[1.0, 0.0], [1.0, 0.0]]]
)
def test_invalid_provider_vectors_fail_closed(runtime, vectors):
    class Broken:
        name, semantic = "broken", True

        def encode(self, texts):
            return vectors

    runtime[0].embedding_provider = Broken()
    before = runtime[0].snapshot()
    response = post(runtime, "menu/prepare", {"content": '["Soup"]'})
    assert response.status_code == 503
    assert runtime[0].snapshot() == before


def test_slow_encoder_does_not_hold_operational_lock(runtime):
    entered, release = Event(), Event()

    class Slow(LocalEmbeddings):
        def encode(self, texts):
            entered.set()
            assert release.wait(3)
            return super().encode(texts)

    runtime[0].embedding_provider = Slow()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            runtime[0].prepare_menu,
            MenuPrepareRequest(content='["Soup"]'),
            runtime[2]["lead-1"],
        )
        assert entered.wait(3)
        try:
            assert start(runtime)
            assert runtime[1].get("/api/v2/state").status_code == 200
        finally:
            release.set()
        assert future.result(timeout=3)["index"]["item_count"] == 1


def test_remote_adapter_orders_vectors_and_sanitizes_failure():
    def handle(request):
        assert request.headers["authorization"] == "Bearer test-key"
        data = json.loads(request.content)
        assert data["input"] == ["Soup", "Salad"]
        assert data["encoding_format"] == "float"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )

    provider = OpenAIEmbeddings(
        "test-key", "test-model", transport=httpx.MockTransport(handle)
    )
    assert provider.encode(["Soup", "Salad"]) == [[1.0, 0.0], [0.0, 1.0]]
    provider = OpenAIEmbeddings(
        "secret-key",
        "test-model",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(429, text="secret-key input content")
        ),
    )
    with pytest.raises(EmbeddingError) as error:
        provider.encode(["sensitive query"])
    assert "secret-key" not in str(error.value) and "sensitive" not in str(error.value)


def test_punctuation_search_and_contract_discovery(runtime):
    assert post(runtime, "menu/search", {"text": "---"}).json()["candidates"] == []
    schemas = runtime[1].get("/api/v2/contracts").json()
    assert {"menu", "menu_prepare", "menu_search"} <= schemas.keys()
    assert load_menu().schema_version == 2


def test_alias_collision_is_visible_and_does_not_auto_match(runtime):
    prepared = prepare(
        runtime,
        [
            {"id": "soup", "name": "Soup", "aliases": ["special"]},
            {"id": "salad", "name": "Salad", "aliases": ["special"]},
        ],
    )
    assert prepared["warnings"] == [
        {
            "code": "ambiguous_item_alias",
            "alias": "special",
            "candidates": ["salad", "soup"],
        }
    ]
    assert activate(runtime, prepared).status_code == 200
    matched = post(runtime, "menu/match", {"text": "special"}).json()
    assert matched["status"] == "ambiguous" and matched["menu_id"] is None


def test_changed_descriptions_rebuild_revision_and_preserve_old_search(runtime):
    first = prepare(runtime)
    assert activate(runtime, first).status_code == 200
    second = prepare(
        runtime,
        [
            {
                "id": "soup",
                "name": "Tomato soup",
                "description": "Chilled cucumber yogurt",
            }
        ],
    )
    assert first["menu_revision"] != second["menu_revision"]
    assert activate(runtime, second).status_code == 200
    old = post(
        runtime,
        "menu/search",
        {"text": "basil", "menu_revision": first["menu_revision"]},
    ).json()
    assert old["menu_revision"] == first["menu_revision"]
    assert old["candidates"][0]["menu_id"] == "soup"
    assert (
        runtime[1].get("/api/v2/menu/index").json()["menu_revision"]
        == second["menu_revision"]
    )


def test_new_ingredient_geometry_requires_explicit_setup(runtime):
    prepared = prepare(
        runtime,
        [
            {
                "id": "soup",
                "name": "Soup",
                "recipe": [
                    {"ingredient": "tomato", "qty": 1, "zone_id": "new-camera-zone"}
                ],
            }
        ],
    )
    before = runtime[0].snapshot()
    response = activate(runtime, prepared)
    assert response.status_code == 409
    assert runtime[0].snapshot() == before


def test_outbox_enqueue_failure_rolls_back_menu_and_active_index(runtime, monkeypatch):
    prepared = prepare(runtime)
    before = runtime[0].snapshot()
    original = runtime[0].outbox.enqueue

    def fail(events):
        raise ValueError("Local enqueue failed")

    monkeypatch.setattr(runtime[0].outbox, "enqueue", fail)
    payload = {
        "action": "activate_menu",
        "candidate_id": prepared["candidate_id"],
        "expected_menu_revision": prepared["expected_menu_revision"],
        "human_confirmed": True,
    }
    envelope = Command(event_id=str(uuid4()), payload=payload)
    with pytest.raises(ValueError, match="Local enqueue"):
        runtime[0].execute(envelope, runtime[2]["lead-1"])
    assert runtime[0].snapshot() == before
    assert (
        runtime[1].get("/api/v2/menu/index").json()["menu_revision"]
        == before["menu_revision"]
    )
    monkeypatch.setattr(runtime[0].outbox, "enqueue", original)
    assert (
        runtime[0].execute(envelope, runtime[2]["lead-1"])["result"]["menu_revision"]
        == prepared["menu_revision"]
    )


def test_demo_artwork_fixture_encodes_eight_items_without_invented_kitchen_fields(
    runtime,
):
    from pathlib import Path

    menu = load_menu(Path(__file__).resolve().parents[1] / "fixtures/menus/dig-in.json")
    assert len(menu.items) == 8
    prepared = post(runtime, "menu/prepare", {"content": menu.model_dump_json()}).json()
    assert prepared["index"]["item_count"] == 8
    assert activate(runtime, prepared).status_code == 200
    assert all(
        item.station is None and item.recipe is None and item.price_cents is None
        for item in menu.items
    )
