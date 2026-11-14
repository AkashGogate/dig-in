"""Contract checks for reusable menus and conservative, transient voice parsing."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.mvp.menu import MenuDocument, import_status, load_menu, match_menu
from app.mvp.voice import parse_kitchen, parse_order, transcribe_discarding

MENU_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "menus"


def test_two_dish_order_matches_menu_ids_modifiers_and_table_not_quantity():
    menu = load_menu()
    parsed = parse_order(menu, "Table 2: one salmon, no butter, and two risotto", "2")
    assert parsed == {
        "table_id": "2",
        "table_mismatch": False,
        "lines": [
            {"menu_id": "salmon", "quantity": 1, "modifiers": ["no_butter"]},
            {"menu_id": "risotto", "quantity": 2, "modifiers": []},
        ],
        "flags": [],
    }
    assert "transcript" not in parsed


def test_second_menu_loads_without_parser_code_changes_and_unknown_kitchen_fields_stay_null():
    menu = load_menu(MENU_DIR / "second.json")
    parsed = parse_order(
        menu, "Table 3: one burger, hold the onions, and one salad", "3"
    )
    assert [line["menu_id"] for line in parsed["lines"]] == ["burger", "salad"]
    assert parsed["lines"][0]["modifiers"] == ["no_onion"]
    assert not parsed["flags"]
    assert all(
        item.station is None and item.typical_minutes is None and item.recipe is None
        for item in menu.items
    )
    status = import_status(menu)
    assert status["live_import_available"] is False
    assert set(status["missing_kitchen_fields"]) == {"burger", "salad"}


def test_env_selects_second_menu(monkeypatch):
    monkeypatch.setenv("DIG_IN_MENU_PATH", str(MENU_DIR / "second.json"))
    assert load_menu().id == "second"


def test_table_mismatch_is_explicit_and_does_not_silently_retarget():
    parsed = parse_order(load_menu(), "Table 2: one salmon", "1")
    assert parsed["table_mismatch"] is True
    assert parsed["table_id"] == "2"
    assert any(flag["code"] == "table_mismatch" for flag in parsed["flags"])


def test_missing_table_does_not_infer_it_from_quantity():
    parsed = parse_order(load_menu(), "two salmon", "2")
    assert parsed["table_id"] is None
    assert parsed["lines"][0]["quantity"] == 2
    assert any(flag["code"] == "table_required" for flag in parsed["flags"])


def test_unknown_item_does_not_destroy_known_line_or_guess():
    parsed = parse_order(load_menu(), "Table 1: one salmon and one lobster", "1")
    assert [line["menu_id"] for line in parsed["lines"]] == ["salmon"]
    assert any(flag["code"] == "unknown_item" for flag in parsed["flags"])


def test_unknown_modifier_is_not_silently_ignored():
    result = match_menu(load_menu(), "salmon extra caviar")
    assert result["menu_id"] == "salmon"
    assert result["status"] == "unknown"
    assert result["modifiers"] == []
    assert result["unmatched_terms"] == ["extra", "caviar"]


def test_same_alias_on_two_items_returns_candidates_without_guess():
    menu = load_menu().model_copy(deep=True)
    for item in menu.items:
        item.aliases.append("special")
    result = match_menu(menu, "special")
    assert result["status"] == "ambiguous"
    assert result["menu_id"] is None
    assert result["candidates"] == ["risotto", "salmon"]


def test_longer_name_wins_only_over_overlapping_shorter_alias():
    menu = MenuDocument.model_validate(
        {
            "id": "longer",
            "name": "Alias boundary fixture",
            "items": [
                {"id": "salad", "name": "Salad"},
                {"id": "chicken_salad", "name": "Chicken salad"},
            ],
        }
    )
    assert match_menu(menu, "chicken salad")["menu_id"] == "chicken_salad"
    assert match_menu(menu, "salad chicken salad")["menu_id"] is None


def test_ambiguous_modifier_returns_flag_and_no_modifier_selection():
    menu = load_menu().model_copy(deep=True)
    for modifier in menu.items[0].modifiers:
        modifier.aliases.append("changed")
    result = match_menu(menu, "salmon changed")
    assert result["modifiers"] == []
    assert any(flag["code"] == "ambiguous_modifier" for flag in result["flags"])


def test_and_in_configured_name_is_not_a_second_dish():
    parsed = parse_order(
        load_menu(), "Table 1: one salmon and greens and one risotto", "1"
    )
    assert len(parsed["lines"]) == 2
    assert not parsed["flags"]


@pytest.mark.parametrize(
    "utterance", ["Table 1: zero salmon", "Table 1: 0 salmon", "Table 1: 13 salmon"]
)
def test_invalid_or_unknown_quantity_stays_flagged(utterance):
    parsed = parse_order(load_menu(), utterance, "1")
    assert parsed["flags"]
    assert all(1 <= line["quantity"] <= 12 for line in parsed["lines"])


def test_kitchen_grammar_does_not_guess_an_order_or_staff_identity():
    menu = load_menu()
    assert parse_kitchen(menu, "Heard, table 2") == {
        "action": "acknowledge",
        "table_id": "2",
        "menu_id": None,
        "flags": [],
    }
    assert parse_kitchen(menu, "Start table 2 salmon")["action"] == "start_dish"
    assert parse_kitchen(menu, "Start table 2 lobster")["action"] is None
    assert parse_kitchen(menu, "yes send everything")["action"] is None


def test_menu_rejects_duplicate_item_ids():
    data = load_menu().model_dump()
    data["items"].append(data["items"][0])
    with pytest.raises(ValidationError):
        MenuDocument.model_validate(data)


def test_mutable_audio_buffer_clears_on_success_and_provider_failure():
    class Provider:
        def transcribe(self, audio, content_type):
            assert audio == b"test-audio"
            return "Table 1 one item"

    audio = bytearray(b"test-audio")
    assert transcribe_discarding(audio, "audio/webm", Provider()) == "Table 1 one item"
    assert not audio

    class FailedProvider:
        def transcribe(self, audio, content_type):
            raise RuntimeError("provider unavailable")

    audio = bytearray(b"test-audio")
    with pytest.raises(RuntimeError):
        transcribe_discarding(audio, "audio/webm", FailedProvider())
    assert not audio
