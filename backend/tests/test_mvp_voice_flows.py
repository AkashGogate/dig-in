"""Voice flow checks: natural kitchen phrasing and the kitchen-voice role gate."""

import test_mvp_core as core

from app.mvp.menu import load_menu
from app.mvp.voice import parse_kitchen

demo = core.demo  # reuse the core MVP fixture


def test_kitchen_phrase_ignores_trailing_filler():
    menu = load_menu()
    assert parse_kitchen(menu, "Heard table two, thanks")["action"] == "acknowledge"
    assert parse_kitchen(menu, "Heard, table 2. Thank you chef.")["table_id"] == "2"
    assert (
        parse_kitchen(menu, "Start table two salmon please")["action"] == "start_dish"
    )


def test_start_phrase_requires_single_physical_unit():
    parsed = parse_kitchen(load_menu(), "Start table four, two salmon.")
    assert parsed["action"] is None and parsed["flags"][0]["code"] == "unit_quantity"
    singular = parse_kitchen(load_menu(), "Start table four one salmon")
    assert singular["action"] == "start_dish" and singular["menu_id"] == "salmon"
    assert parsed["table_id"] == "4"


def test_unsupported_phrases_stay_unsupported():
    menu = load_menu()
    for text in ("yes send everything", "thanks chef", "heard", "start the salmon"):
        assert parse_kitchen(menu, text)["action"] is None


def test_server_session_cannot_use_kitchen_voice(demo):
    response = core.send(
        demo,
        {"action": "kitchen_voice", "text": "Heard, table 1"},
        actor="server-1",
        source="voice",
    )
    assert response.status_code == 409
