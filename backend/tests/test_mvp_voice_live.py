"""Live-voice adapter checks with a fake Deepgram: no key, no network, no spend."""

import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import test_mvp_core as core
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.mvp import voice_live
from app.mvp.menu import load_menu
from app.mvp.voice import parse_kitchen, parse_order
from app.server import app

demo = core.demo  # reuse the core MVP fixture
DIG_IN = Path(__file__).resolve().parents[1] / "fixtures" / "menus" / "dig-in.json"


class FakeDeepgram:
    def __init__(self, script):
        self.script, self.sent, self.queue = script, [], asyncio.Queue()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, data):
        self.sent.append(data)
        if isinstance(data, str) and json.loads(data)["type"] == "CloseStream":
            for event in self.script:
                await self.queue.put(json.dumps(event))
            await self.queue.put(None)

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.queue.get()
        if item is None:
            raise StopAsyncIteration
        return item


def results(text, final):
    return {
        "type": "Results",
        "is_final": final,
        "channel": {"alternatives": [{"transcript": text}]},
    }


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("DIG_IN_VOICE_LIVE", "1")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key-not-real")
    monkeypatch.delenv("DEMO_AUTH_USER", raising=False)
    monkeypatch.delenv("DEMO_AUTH_PASS", raising=False)
    monkeypatch.setattr(voice_live, "budget", voice_live.VoiceBudget())
    fakes = []

    def connect(url, additional_headers):
        assert additional_headers == {"Authorization": "Token test-key-not-real"}
        fake = FakeDeepgram(
            [
                results("table four two", False),
                results("Table 4: two bulldozers, hold the pickles", True),
                {"type": "Metadata", "duration": 3.5},
            ]
        )
        fake.url = url
        fakes.append(fake)
        return fake

    monkeypatch.setattr(voice_live, "deepgram_connect", connect)
    return fakes


def test_dig_in_menu_parses_spoken_orders_with_plurals_and_modifiers():
    menu = load_menu(DIG_IN)
    parsed = parse_order(
        menu, "Table 4: two bulldozers, hold the pickles, and one dirt site", "4"
    )
    assert parsed["lines"] == [
        {"menu_id": "bulldozer", "quantity": 2, "modifiers": ["no_pickles"]},
        {"menu_id": "dirt_site", "quantity": 1, "modifiers": []},
    ]
    assert not parsed["flags"]
    assert (
        parse_order(menu, "Table 1: one mac and cheese", "1")["lines"][0]["menu_id"]
        == "cement_mixer_mac"
    )
    assert parse_kitchen(menu, "Start table 4 bulldozer")["action"] == "start_dish"


def test_keyterms_come_from_menu_and_url_opts_out_of_retention_without_diarization():
    menu = load_menu(DIG_IN)
    terms = voice_live.keyterms(menu)
    assert {
        "The Bulldozer",
        "bulldozers",
        "Gravel Pit Tots",
        "No pickles",
        "table",
        "heard",
    } <= set(terms)
    assert len(terms) == len(set(terms)) <= voice_live.MAX_KEYTERMS
    query = parse_qs(urlsplit(voice_live.listen_url(menu)).query)
    assert query["model"] == ["nova-3"] and query["mip_opt_out"] == ["true"]
    assert "diarize" not in query and "The Bulldozer" in query["keyterm"]


def test_budget_caps_daily_spend_concurrency_and_reports_cost(monkeypatch):
    monkeypatch.setenv("DIG_IN_VOICE_DAILY_MINUTES", "1")
    monkeypatch.setenv("DIG_IN_VOICE_MAX_STREAM_SECONDS", "30")
    monkeypatch.setenv("DIG_IN_DEEPGRAM_USD_PER_MINUTE", "0.01")
    b = voice_live.VoiceBudget()
    assert b.start("a") == 30
    with pytest.raises(voice_live.VoiceLimit):
        b.start("a")  # one open capture per device
    b.finish("a", 45)
    assert b.start("b") == 15  # stream cap shrinks to remaining daily budget
    b.finish("b", 15)
    with pytest.raises(voice_live.VoiceLimit):
        b.start("c")
    usage = b.usage()
    assert usage["audio_seconds_used"] == 60 and usage["estimated_usd_used"] == 0.01
    assert usage["streams_rejected"] == {"ip_active": 1, "daily_budget": 1}


def test_ticket_is_off_unless_live_enabled(monkeypatch):
    monkeypatch.delenv("DIG_IN_VOICE_LIVE", raising=False)
    assert TestClient(app).post("/api/v2/voice/ticket").status_code == 503


def test_ticket_requires_demo_password_when_configured(live, monkeypatch):
    monkeypatch.setenv("DEMO_AUTH_USER", "u")
    monkeypatch.setenv("DEMO_AUTH_PASS", "p")
    client = TestClient(app)
    assert client.post("/api/v2/voice/ticket").status_code == 401
    assert client.post("/api/v2/voice/ticket", auth=("u", "wrong")).status_code == 401
    assert client.post("/api/v2/voice/ticket", auth=("u", "p")).status_code == 200
    assert client.get("/api/v2/voice/usage").status_code == 401


def test_stream_relays_transcript_records_billed_seconds_and_ticket_is_single_use(live):
    client = TestClient(app)
    ticket = client.post("/api/v2/voice/ticket").json()["ticket"]
    with client.websocket_connect(f"/api/v2/voice/stream?ticket={ticket}") as ws:
        ws.send_bytes(b"opus-chunk")
        ws.send_text(json.dumps({"type": "stop"}))
        messages = []
        while not messages or messages[-1]["type"] != "done":
            messages.append(ws.receive_json())
    assert [m["type"] for m in messages] == ["interim", "final", "done"]
    assert messages[-1]["text"] == "Table 4: two bulldozers, hold the pickles"
    assert live[0].sent[0] == b"opus-chunk"
    assert voice_live.budget.usage()["audio_seconds_used"] == 3.5
    assert voice_live.budget.usage()["active_streams"] == 0
    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect(f"/api/v2/voice/stream?ticket={ticket}") as ws:
            ws.receive_json()
    assert closed.value.code == 4401


def test_voice_status_reports_live_mode(live):
    status = TestClient(app).get("/api/v2/voice/status").json()
    assert (
        status["mode"] == "deepgram_stream" and status["live_capture_available"] is True
    )
    assert status["discard_audio_after_transcription"] is True


def test_real_deepgram_transcript_with_spelled_numbers_parses_cleanly():
    """Regression from the first live run: nova-3 returned 'Table four. Two bulldozers.'"""
    menu = load_menu(DIG_IN)
    parsed = parse_order(
        menu, "Table four. Two bulldozers. Hold the pickles. And one dirt site.", "4"
    )
    assert parsed["table_id"] == "4" and not parsed["flags"]
    assert parsed["lines"] == [
        {"menu_id": "bulldozer", "quantity": 2, "modifiers": ["no_pickles"]},
        {"menu_id": "dirt_site", "quantity": 1, "modifiers": []},
    ]
    assert parse_kitchen(menu, "Heard, table four.")["table_id"] == "4"
    assert parse_kitchen(menu, "Start table four bulldozer.")["action"] == "start_dish"


def _voice_capture(demo, mode=None):
    key = core.ok(demo, {"action": "start_order", "table_id": "1"})["result"][
        "order_id"
    ]
    payload = {
        "action": "capture_voice",
        "order_id": key,
        "revision": 1,
        "text": "Table 1: one salmon",
    }
    if mode:
        payload["capture_mode"] = mode
    return key, core.send(demo, payload, source="voice")


def test_capture_mode_defaults_to_mock_and_live_label_needs_live_server(
    demo, monkeypatch
):
    monkeypatch.delenv("DIG_IN_VOICE_LIVE", raising=False)
    key, response = _voice_capture(demo)
    assert response.status_code == 200
    assert core.snapshot(demo)["orders"][key]["capture_mode"] == "mock_voice"
    _, refused = _voice_capture(demo, "live_voice")
    assert refused.status_code == 409  # browser can't mislabel typed text as live


def test_live_capture_is_labeled_live_in_state_and_analytics(demo, live):
    key, response = _voice_capture(demo, "live_voice")
    assert response.status_code == 200
    assert core.snapshot(demo)["orders"][key]["capture_mode"] == "live_voice"
    events = [e for e in demo[2].snapshot()["events"] if e["type"] == "draft.updated"]
    assert events[-1]["payload"]["capture_mode"] == "live_voice"


def test_kitchen_voice_with_spoken_numbers_acknowledges_and_starts(demo):
    key = core.order(demo, table="3")
    heard = core.ok(
        demo,
        {"action": "kitchen_voice", "text": "Heard, table three."},
        actor="cook-1",
        source="voice",
    )
    assert not heard["result"].get("flags")
    assert core.snapshot(demo)["orders"][key]["acknowledged_at"] is not None
    core.ok(
        demo,
        {"action": "kitchen_voice", "text": "Start table three salmon."},
        actor="cook-1",
        source="voice",
    )
    assert core.units(demo, key)[0]["started_at"] is not None
