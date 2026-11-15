"""Server-flow voice extras: seats, dietary notes and the ask-the-table reminder."""

from pathlib import Path

import pytest
import test_mvp_core as core

from app.mvp.menu import load_menu
from app.mvp.voice import parse_order

demo = core.demo  # reuse the core MVP fixture
DIG_IN = Path(__file__).resolve().parents[1] / "fixtures" / "menus" / "dig-in.json"


@pytest.fixture
def gated(monkeypatch):
    monkeypatch.setenv("DIG_IN_REQUIRE_DIETARY_CHECK", "1")


def start(demo, table="1"):
    return core.ok(demo, {"action": "start_order", "table_id": table})["result"][
        "order_id"
    ]


def draft(demo, key):
    return core.snapshot(demo)["orders"][key]


def codes(demo, key):
    return [f["code"] for f in draft(demo, key)["flags"]]


def resolve(demo, key, code, resolution):
    order = draft(demo, key)
    flag = next(f for f in order["flags"] if f["code"] == code)
    return core.send(
        demo,
        {
            "action": "resolve_flag",
            "order_id": key,
            "revision": order["revision"],
            "flag_id": flag["id"],
            "resolution": resolution,
        },
    )


def capture(demo, key, text):
    return core.ok(
        demo,
        {
            "action": "capture_voice",
            "order_id": key,
            "revision": draft(demo, key)["revision"],
            "text": text,
        },
        source="voice",
    )


def edit(demo, key, requests):
    return core.ok(
        demo,
        {
            "action": "edit_draft",
            "order_id": key,
            "revision": draft(demo, key)["revision"],
            "table_id": "1",
            "lines": [
                {"id": "l1", "menu_id": "salmon", "quantity": 1, "requests": requests}
            ],
        },
    )


def confirm(demo, key):
    return core.send(
        demo,
        {
            "action": "confirm_send",
            "order_id": key,
            "revision": draft(demo, key)["revision"],
            "human_confirmed": True,
        },
    )


def submitted_payload(demo, key):
    events = demo[2].snapshot()["events"]
    return next(
        e["payload"]
        for e in events
        if e["type"] == "order.submitted" and e["order_id"] == key
    )


def test_parser_extracts_seat_and_dietary_note_per_dish():
    parsed = parse_order(
        load_menu(DIG_IN),
        "Table 2: one bulldozer seat two allergy to gluten and one dirt site",
        "2",
    )
    assert parsed["lines"] == [
        {
            "menu_id": "the_bulldozer",
            "quantity": 1,
            "modifiers": [],
            "seat": 2,
            "requests": "allergy to gluten",
        },
        {"menu_id": "dirt_site", "quantity": 1, "modifiers": []},
    ]
    assert [f["code"] for f in parsed["flags"]] == ["dietary_review"]
    assert parsed["dietary_check"] == "requests_recorded"


def test_parser_records_no_allergies_and_never_drops_an_unattached_note():
    menu = load_menu(DIG_IN)
    clean = parse_order(menu, "Table 1: one steel beams and no allergies", "1")
    assert clean["dietary_check"] == "none_reported" and not clean["flags"]
    lost = parse_order(menu, "Table 1: one lobster allergy to nuts", "1")
    assert "dietary_unattached" in {f["code"] for f in lost["flags"]}
    assert "dietary_check" not in lost


def test_menu_alias_containing_a_trigger_word_stays_a_dish():
    menu = load_menu(DIG_IN).model_copy(deep=True)
    menu.items[0].aliases.append("vegan tots")
    parsed = parse_order(menu, "Table 1: one vegan tots", "1")
    assert parsed["lines"] == [
        {"menu_id": "gravel_pit_tots", "quantity": 1, "modifiers": []}
    ]


def test_reminder_is_off_unless_enabled(demo, monkeypatch):
    monkeypatch.delenv("DIG_IN_REQUIRE_DIETARY_CHECK", raising=False)
    assert codes(demo, start(demo)) == []


def test_reminder_survives_capture_and_blocks_send_until_answer_recorded(demo, gated):
    key = start(demo)
    assert codes(demo, key) == ["dietary_check_required"]
    capture(demo, key, "Table 1: one salmon")
    assert codes(demo, key) == ["dietary_check_required"]
    assert confirm(demo, key).status_code == 409
    assert (
        resolve(
            demo, key, "dietary_check_required", "reviewed_remove_unknown"
        ).status_code
        == 409
    )
    assert (
        resolve(demo, key, "dietary_check_required", "asked_none_reported").status_code
        == 200
    )
    assert draft(demo, key)["dietary_check"] == "none_reported"
    assert confirm(demo, key).status_code == 200
    assert submitted_payload(demo, key)["dietary_check"] == "none_reported"


def test_spoken_dietary_note_records_answer_and_needs_review(demo, gated):
    key = start(demo)
    capture(demo, key, "Table 1: one salmon seat 2 allergy to shellfish")
    order = draft(demo, key)
    assert codes(demo, key) == ["dietary_review"]
    assert order["dietary_check"] == "requests_recorded"
    assert (order["lines"][0]["seat"], order["lines"][0]["requests"]) == (
        2,
        "allergy to shellfish",
    )
    assert confirm(demo, key).status_code == 409
    assert resolve(demo, key, "dietary_review", "reviewed_keep_note").status_code == 200
    assert confirm(demo, key).status_code == 200
    payload = submitted_payload(demo, key)
    assert payload["dietary_check"] == "requests_recorded"
    assert payload["dishes"][0]["requests"] == "allergy to shellfish"


def test_typed_request_records_answer_and_removing_it_asks_again(demo, gated):
    key = start(demo)
    edit(demo, key, "no nuts")
    assert codes(demo, key) == []
    assert draft(demo, key)["dietary_check"] == "requests_recorded"
    edit(demo, key, "")
    assert codes(demo, key) == ["dietary_check_required"]
    assert draft(demo, key)["dietary_check"] == "not_asked"


def test_recapture_without_notes_reopens_the_question(demo, gated):
    key = start(demo)
    capture(demo, key, "Table 1: one salmon allergy to shellfish")
    capture(demo, key, "Table 1: one risotto")
    assert codes(demo, key) == ["dietary_check_required"]


def test_spoken_seat_not_at_table_is_flagged_not_kept(demo):
    key = start(demo)
    capture(demo, key, "Table 1: one salmon seat nine")
    assert draft(demo, key)["lines"][0]["seat"] is None
    assert "seat_unknown" in codes(demo, key)


def test_confirm_blocked_only_by_dietary_check_names_the_real_reason(demo, monkeypatch):
    monkeypatch.setenv("DIG_IN_REQUIRE_DIETARY_CHECK", "1")
    key = core.ok(demo, {"action": "start_order", "table_id": "1"})["result"][
        "order_id"
    ]
    core.ok(
        demo,
        {
            "action": "edit_draft",
            "order_id": key,
            "revision": 1,
            "table_id": "1",
            "lines": [{"id": "l1", "menu_id": "salmon", "quantity": 1}],
        },
    )
    blocked = core.send(
        demo,
        {
            "action": "confirm_send",
            "order_id": key,
            "revision": 2,
            "human_confirmed": True,
        },
    )
    assert blocked.status_code == 409 and "allergies" in blocked.json()["detail"]


def test_unattached_dietary_note_cannot_be_dismissed_and_survives_attachment(demo):
    key = start(demo)
    capture(demo, key, "Table 1: allergy to nuts and one salmon")
    assert "dietary_unattached" in codes(demo, key)
    assert (
        resolve(demo, key, "dietary_unattached", "reviewed_keep_note").status_code
        == 409
    )
    order = draft(demo, key)
    flag = next(f for f in order["flags"] if f["code"] == "dietary_unattached")
    response = core.send(
        demo,
        {
            "action": "resolve_flag",
            "order_id": key,
            "revision": order["revision"],
            "flag_id": flag["id"],
            "resolution": "reviewed_keep_note",
            "line_id": order["lines"][0]["id"],
        },
    )
    assert response.status_code == 200
    assert draft(demo, key)["lines"][0]["requests"] == "allergy to nuts"
    assert confirm(demo, key).status_code == 200
    assert submitted_payload(demo, key)["dishes"][0]["requests"] == "allergy to nuts"


def test_dietary_review_binds_matched_output_line_after_unknown_clause(demo):
    key = start(demo)
    capture(demo, key, "Table 1: one lobster and one salmon allergy to nuts")
    order = draft(demo, key)
    flag = next(f for f in order["flags"] if f["code"] == "dietary_review")
    assert flag["line_id"] == order["lines"][0]["id"]
    assert resolve(demo, key, "dietary_review", "reviewed_keep_note").status_code == 200


def test_attaching_unattached_note_clears_opt_in_question(demo, gated):
    key = start(demo)
    capture(demo, key, "Table 1: allergy to nuts and one salmon")
    order = draft(demo, key)
    assert "dietary_check_required" in codes(demo, key)
    flag = next(f for f in order["flags"] if f["code"] == "dietary_unattached")
    response = core.send(
        demo,
        {
            "action": "resolve_flag",
            "order_id": key,
            "revision": order["revision"],
            "flag_id": flag["id"],
            "resolution": "reviewed_keep_note",
            "line_id": order["lines"][0]["id"],
        },
    )
    assert response.status_code == 200
    assert "dietary_check_required" not in codes(demo, key)
    assert draft(demo, key)["dietary_check"] == "requests_recorded"
    assert confirm(demo, key).status_code == 200
