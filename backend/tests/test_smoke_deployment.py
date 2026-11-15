"""The release probe must fail cleanly on older or malformed hosted snapshots."""

import json
import sys
from urllib.parse import urlsplit

import httpx
import pytest

from scripts import smoke_deployment


@pytest.mark.parametrize("state", [{"schema_version": 2}, [], None])
def test_old_or_invalid_state_reports_failure_without_crashing(
    monkeypatch, capsys, state
):
    _hosted(monkeypatch, state=state)
    assert smoke_deployment.main() == 1
    report = json.loads(capsys.readouterr().out)
    checks = {c["check"]: c for c in report["checks"]}
    assert not report["passed"]
    assert not checks["backend_login"]["passed"]
    assert not checks["frontend_proxy"]["passed"]
    assert "shared_menu_revision" not in checks


def test_matching_current_release_passes_and_live_mode_is_required(monkeypatch, capsys):
    _hosted(monkeypatch, state={"schema_version": 2, "menu_revision": "reviewed"})
    assert smoke_deployment.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["passed"]
    assert all(c["passed"] for c in report["checks"])
    monkeypatch.setattr(sys, "argv", ["smoke_deployment", "--require-live-voice"])
    assert smoke_deployment.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert not next(c for c in report["checks"] if c["check"] == "voice_mode")["passed"]


@pytest.mark.parametrize("voice", [[], {"mode": []}, {"mode": {}}])
def test_malformed_voice_status_fails_cleanly(monkeypatch, capsys, voice):
    _hosted(
        monkeypatch,
        state={"schema_version": 2, "menu_revision": "reviewed"},
        voice=voice,
    )
    assert smoke_deployment.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert not next(c for c in report["checks"] if c["check"] == "voice_mode")["passed"]


def _hosted(monkeypatch, *, state, voice=None):
    monkeypatch.setenv("DEMO_AUTH_USER", "probe-only-user")
    monkeypatch.setenv("DEMO_AUTH_PASS", "probe-only-value")
    monkeypatch.setattr(sys, "argv", ["smoke_deployment"])

    def get(url, *, auth=None, **kwargs):
        path = urlsplit(url).path
        if path == "/healthz":
            return httpx.Response(200, json={"status": "ok", "schema_version": 2})
        if auth is None:
            return httpx.Response(
                401, headers={"www-authenticate": 'Basic realm="demo"'}
            )
        if path == "/":
            return httpx.Response(
                200, text="demo", headers={"content-type": "text/html"}
            )
        if path == "/api/v2/state":
            return httpx.Response(200, content=json.dumps(state))
        assert path == "/api/v2/voice/status"
        return httpx.Response(
            200, json={"mode": "mock_transcript"} if voice is None else voice
        )

    monkeypatch.setattr(smoke_deployment.httpx, "get", get)
