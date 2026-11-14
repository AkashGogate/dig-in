"""Voice flow checks: natural kitchen phrasing and the kitchen-voice role gate."""

from pathlib import Path

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


def test_start_phrase_drops_leading_quantity():
    parsed = parse_kitchen(load_menu(), "Start table four, two salmon.")
    assert parsed["action"] == "start_dish" and parsed["menu_id"] == "salmon"
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


def test_live_homophones_only_count_in_the_table_slot():
    """Regressions from the first live DIG IN eval run (nova-3 transcripts)."""
    from app.mvp.menu import load_menu as _load
    from app.mvp.voice import parse_kitchen as _kitchen
    from app.mvp.voice import parse_order as _order

    menu = _load(Path(__file__).resolve().parents[1] / "fixtures/menus/dig-in.json")
    started = _kitchen(menu, "Start table for bulldozer")
    assert started["action"] == "start_dish" and started["table_id"] == "4"
    assert _order(menu, "Table to, one tots", "2")["table_id"] == "2"
    # smart_format used to merge "three, one backhoe" into "31": must block, never accept.
    merged = _order(menu, "Table 31 backhoe without slaw", "3")
    assert {f["code"] for f in merged["flags"]} >= {"table_mismatch"}
