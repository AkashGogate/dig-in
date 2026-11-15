"""Bounded deployment polling uses sanitized read-only probes, never live calls."""

import argparse
import json
from pathlib import Path

import httpx
import pytest

from scripts import monitor_deployment as monitor
from scripts import smoke_deployment


@pytest.fixture
def credentials(monkeypatch):
    monkeypatch.setenv("DEMO_AUTH_USER", "test-user")
    monkeypatch.setenv("DEMO_AUTH_PASS", "test-secret")


def outcome(passed):
    return {
        "passed": passed,
        "checks": [
            {
                "check": "frontend_login",
                "passed": passed,
                "status": 200 if passed else 503,
            }
        ],
    }


def test_recovery_stops_early_and_preserves_live_option(credentials):
    calls, waits = [], []
    sequence = iter([outcome(False), outcome(True)])

    def probe(*args):
        calls.append(args)
        return next(sequence)

    result = monitor.monitor(
        "https://front",
        "https://back",
        True,
        attempts=5,
        interval_seconds=2,
        probe_fn=probe,
        sleep_fn=waits.append,
    )
    assert result["passed"]
    assert [row["attempt"] for row in result["attempts"]] == [1, 2]
    assert calls == [("https://front", "https://back", True)] * 2
    assert waits == [2]


def test_exhausted_failure_sleeps_only_between_attempts(credentials):
    waits = []
    result = monitor.monitor(
        "https://front",
        "https://back",
        attempts=3,
        interval_seconds=0,
        probe_fn=lambda *_: outcome(False),
        sleep_fn=waits.append,
    )
    assert not result["passed"] and len(result["attempts"]) == 3
    assert waits == [0, 0]


@pytest.mark.parametrize(
    "user,password", [(None, None), ("user", None), (None, "secret"), ("", "secret")]
)
def test_missing_credentials_do_not_probe_or_wait(monkeypatch, user, password):
    for key, value in [("DEMO_AUTH_USER", user), ("DEMO_AUTH_PASS", password)]:
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    def forbidden(*_):
        pytest.fail("missing credentials must not call network or sleep")

    result = monitor.monitor(
        "https://front", "https://back", probe_fn=forbidden, sleep_fn=forbidden
    )
    assert result == {
        "passed": False,
        "attempts": [],
        "error": "credential_environment_unavailable",
    }


@pytest.mark.parametrize(
    "attempts,interval",
    [
        (0, 0),
        (11, 0),
        (-1, 0),
        (1.5, 0),
        (True, 0),
        (1, -1),
        (1, 61),
        (1, float("inf")),
        (1, float("nan")),
    ],
)
def test_invalid_bounds_reject_before_poll(attempts, interval):
    with pytest.raises(ValueError):
        monitor.monitor(
            "https://front",
            "https://back",
            attempts=attempts,
            interval_seconds=interval,
        )


def test_maximum_bounds_are_allowed_without_real_wait(credentials):
    waits = []
    result = monitor.monitor(
        "https://front",
        "https://back",
        attempts=10,
        interval_seconds=60,
        probe_fn=lambda *_: outcome(False),
        sleep_fn=waits.append,
    )
    assert len(result["attempts"]) == 10 and waits == [60] * 9


def test_network_exception_never_leaks_message(credentials):
    def broken(*_):
        raise httpx.ConnectError(
            "test-secret raw body transcript https://user:password@example.com"
        )

    result = monitor.monitor(
        "https://front", "https://back", attempts=1, probe_fn=broken
    )
    assert result["attempts"] == [
        {"attempt": 1, "passed": False, "checks": [], "error": "probe_failed"}
    ]
    assert "test-secret" not in json.dumps(result)
    assert "transcript" not in json.dumps(result)


def test_cli_outputs_one_final_json_and_writes_temporary_artifact(
    credentials, monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(smoke_deployment, "probe", lambda *_: outcome(True))
    path = tmp_path / "report.json"
    assert (
        monitor.main(
            [
                "--attempts",
                "3",
                "--interval-seconds",
                "0",
                "--require-live-voice",
                "--report-file",
                str(path),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["passed"] and len(report["attempts"]) == 1
    assert json.loads(path.read_text()) == report
    assert "test-secret" not in path.read_text()


def test_cli_missing_credentials_returns_clear_nonzero_json(monkeypatch, capsys):
    monkeypatch.delenv("DEMO_AUTH_USER", raising=False)
    monkeypatch.delenv("DEMO_AUTH_PASS", raising=False)
    assert monitor.main([]) == 1
    assert (
        json.loads(capsys.readouterr().out)["error"]
        == "credential_environment_unavailable"
    )


@pytest.mark.parametrize(
    "args",
    [["--attempts", "11"], ["--interval-seconds", "nan"], ["--interval-seconds", "-1"]],
)
def test_cli_invalid_bounds_fail_clearly(args, capsys):
    with pytest.raises(SystemExit) as exc:
        monitor.main(args)
    assert exc.value.code == 2
    assert not capsys.readouterr().out


def test_report_path_rejects_tracked_source_even_when_repository_is_in_tmp():
    with pytest.raises(argparse.ArgumentTypeError):
        monitor.report_destination(str(Path(monitor.__file__).resolve()))


def test_reusable_probe_returns_checks_without_printing(monkeypatch, capsys):
    monkeypatch.setenv("DEMO_AUTH_USER", "test-user")
    monkeypatch.setenv("DEMO_AUTH_PASS", "test-secret")
    requests = []

    def get(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(503, text="test-secret raw transcript")

    monkeypatch.setattr(smoke_deployment.httpx, "get", get)
    result = smoke_deployment.probe("https://front", "https://back", require_live=True)
    assert not result["passed"] and len(requests) == 10
    assert not capsys.readouterr().out
    assert all(
        kwargs["timeout"] == 15 and kwargs["follow_redirects"] is False
        for _, kwargs in requests
    )
    assert "test-secret" not in json.dumps(result) and "transcript" not in json.dumps(
        result
    )


def test_cli_unhealthy_exits_nonzero_with_final_attempts(
    credentials, monkeypatch, capsys
):
    monkeypatch.setattr(smoke_deployment, "probe", lambda *_: outcome(False))
    assert monitor.main(["--attempts", "1", "--interval-seconds", "0"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert not report["passed"] and len(report["attempts"]) == 1


def test_report_write_failure_is_sanitized(credentials, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(smoke_deployment, "probe", lambda *_: outcome(True))

    def failed_write(*_):
        raise OSError("test-secret response body")

    monkeypatch.setattr(Path, "write_text", failed_write)
    assert monitor.main(["--report-file", str(tmp_path / "report.json")]) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["error"] == "report_write_failed"
    assert "test-secret" not in output and "response body" not in output


def test_github_runner_temp_outside_system_tmp_is_allowed(monkeypatch):
    monkeypatch.setenv("RUNNER_TEMP", "/home/runner/work/_temp")
    path = "/home/runner/work/_temp/live-readiness.json"
    assert monitor.report_destination(path) == Path(path).resolve()


def test_runner_temp_never_overrides_tracked_source_guard(monkeypatch):
    source = Path(monitor.__file__).resolve()
    monkeypatch.setenv("RUNNER_TEMP", str(source.parents[2]))
    with pytest.raises(argparse.ArgumentTypeError):
        monitor.report_destination(str(source))


@pytest.mark.parametrize("runner_temp", ["relative/path", "/"])
def test_invalid_runner_temp_cannot_allow_arbitrary_destinations(
    monkeypatch, runner_temp
):
    monkeypatch.setenv("RUNNER_TEMP", runner_temp)
    with pytest.raises(argparse.ArgumentTypeError):
        monitor.report_destination("/home/runner/work/_temp/live-readiness.json")
