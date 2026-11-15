"""Kitchen ack/start record whether live kitchen voice was available (fallback metric)."""

import pytest
import test_mvp_core as core

from app.analytics.analyze import analyze
from app.analytics.events import CanonicalEvent

demo = core.demo


def _kitchen_events(demo):
    return [
        e
        for e in demo[2].snapshot()["events"]
        if e["type"] in ("order.acknowledged", "dish.started")
    ]


def _automation(demo):
    events = [CanonicalEvent.model_validate(e) for e in demo[2].snapshot()["events"]]
    return analyze(events)["automation"]


def _tap_ack_and_start(demo, table="1"):
    key = core.order(demo, table=table)
    core.ack(demo, key)
    core.dish_action(demo, core.units(demo, key)[0]["id"], "start_dish")
    return key


@pytest.fixture
def live_off(monkeypatch):
    monkeypatch.delenv("DIG_IN_VOICE_LIVE", raising=False)


@pytest.fixture
def live_on(monkeypatch):
    monkeypatch.setenv("DIG_IN_VOICE_LIVE", "1")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "fake-not-real")


def test_taps_with_live_voice_off_are_confirmed_unavailable(demo, live_off):
    _tap_ack_and_start(demo)
    events = _kitchen_events(demo)
    assert [e["type"] for e in events] == ["order.acknowledged", "dish.started"]
    for event in events:
        assert event["payload"]["automation_available"] is False
        assert "Live kitchen voice is off" in event["payload"]["fallback_reason"]
    automation = _automation(demo)
    assert automation["confirmed_unavailable_tap_actions"] == 2
    assert automation["unknown_availability_tap_actions"] == 0


def test_taps_with_live_voice_on_are_manual_choice_not_fallback(demo, live_on):
    _tap_ack_and_start(demo)
    for event in _kitchen_events(demo):
        assert event["payload"]["automation_available"] is True
        assert event["payload"]["fallback_reason"] is None
    automation = _automation(demo)
    assert automation["tap_actions"] == 2
    assert automation["confirmed_unavailable_tap_actions"] == 0
    assert automation["availability_known_actions"] == 2


def test_voice_sourced_ack_and_start_count_as_automation(demo, live_off):
    key = core.order(demo, table="3")
    for text in ("Heard, table three", "Start table three salmon"):
        core.ok(
            demo,
            {"action": "kitchen_voice", "text": text},
            actor="cook-1",
            source="voice",
        )
    assert core.units(demo, key)[0]["started_at"] is not None
    for event in _kitchen_events(demo):
        assert event["source"] == "voice"
        assert event["payload"]["automation_available"] is True
        assert event["payload"]["fallback_reason"] is None
    automation = _automation(demo)
    assert automation["eligible_actions"] == 2 and automation["tap_actions"] == 0
    assert automation["manual_action_share"] == 0
