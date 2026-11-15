"""Coval-style DIG IN voice harness: CI-safe (no network, no `say`, no spend)."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit

import httpx
import numpy as np
import pytest

from app.mvp.voice_live import listen_url
from eval.dig_in import audio, metrics, run, simulate


def _mock_run(tmp_path, *extra):
    code = run.main(["--runs-dir", str(tmp_path), *extra])
    record = json.loads(next(tmp_path.glob("*.json")).read_text())
    return code, record


def test_mock_run_covers_both_flows_with_zero_wrong(tmp_path, monkeypatch):
    def no_external(*args, **kwargs):
        raise AssertionError("mock must not call providers or render audio")

    monkeypatch.setattr(httpx, "post", no_external)
    monkeypatch.setattr(audio, "ensure_clip", no_external)
    code, record = _mock_run(tmp_path)
    assert code == 0 and record["gate_passed"]
    outcomes = [r["metrics"]["safety_outcome"] for r in record["results"]]
    assert "wrong" not in outcomes
    assert {r["flow"] for r in record["results"]} == {"server", "kitchen"}
    assert set(record["test_sets"]) == {
        "server_orders",
        "kitchen_callouts",
        "safety_regressions",
    }
    scripted = [r for r in record["results"] if r["persona"] == run.MOCK_PERSONA]
    assert scripted and all(r["metrics"]["safety_outcome"] == "exact" for r in scripted)
    assert (
        (tmp_path / (record["run_id"] + ".md"))
        .read_text()
        .startswith("# DIG IN voice run")
    )


def test_every_real_live_transcript_is_exact_or_safely_flagged(tmp_path):
    _, record = _mock_run(tmp_path, "--test-set", "safety_regressions")
    assert len(record["results"]) == 9
    for r in record["results"]:
        assert r["metrics"]["safety_outcome"] in ("exact", "flagged"), r["heard"]
        if "controlled_confidence" in r["tags"]:
            assert r["metrics"]["wer"] is None
            assert r["persona"] == run.CONTROLLED_PERSONA
        else:
            assert r["metrics"]["wer"] is not None


def test_kitchen_wrong_means_a_real_wrong_state_change():
    menu = run.load_menu(run.MENU_PATH)
    case = {
        "flow": "kitchen",
        "utterance": "Heard, table four",
        "context": [
            {
                "label": "T1",
                "table_id": "1",
                "lines": [{"menu_id": "the_backhoe", "quantity": 1}],
                "state": "submitted",
            },
            {
                "label": "T4",
                "table_id": "4",
                "lines": [{"menu_id": "the_bulldozer", "quantity": 1}],
                "state": "submitted",
            },
        ],
        "expected_any": [{"acknowledged": ["T4"], "started": []}],
    }
    misheard = simulate.observe(case, "Heard, table one", menu)
    assert misheard["acknowledged"] == ["T1"]
    sim = {
        "stt": False,
        "heard": "Heard, table one",
        "scripted": case["utterance"],
        "menu": menu,
    }
    assert metrics.score(case, misheard, sim)["safety_outcome"] == "wrong"


def test_server_wrong_means_sendable_with_wrong_content():
    line = {"menu_id": "the_bulldozer", "quantity": 2, "modifiers": []}
    case = {
        "flow": "server",
        "expected_any": [{"table_id": "4", "lines": [line], "flag_codes": []}],
    }
    actual = {"table_id": "4", "lines": [dict(line, quantity=3)], "flag_codes": []}
    expected, passed = metrics.best_expected(case, actual)
    assert not passed
    assert metrics.outcome("server", actual, passed) == "wrong"
    assert metrics.quantity_accuracy(case, actual, expected, {}) == 0
    flagged = dict(actual, flag_codes=["table_mismatch"])
    assert metrics.outcome("server", flagged, False) == "flagged"


def test_metric_functions():
    assert (
        metrics.word_error_rate("table four two bulldozers", "table for two bulldozers")
        == 0.25
    )
    assert metrics.word_error_rate("heard table four", "heard table four") == 0
    menu = run.load_menu(run.MENU_PATH)
    said = "two bulldozers and one dirt site"
    assert (
        metrics.menu_term_hits(menu, said, "two bulldozers and one dirt sight") == 0.5
    )
    case = {"flow": "server"}
    note = {"seat": 2, "requests": "allergy to gluten"}
    actual = {
        "lines": [dict(note, menu_id="bulldozer", quantity=1, modifiers=[])],
        "dietary_check": "requests_recorded",
    }
    expected = {
        "lines": [dict(note, menu_id="bulldozer", quantity=2, modifiers=[])],
        "dietary_check": "requests_recorded",
    }
    assert metrics.item_precision(case, actual, expected, {}) == 1.0
    assert metrics.item_recall(case, actual, expected, {}) == 0.5
    assert metrics.seat_dietary_capture(case, actual, expected, {}) == 1.0
    assert (
        metrics.wer(
            case, actual, expected, {"stt": False, "heard": "x", "scripted": "y"}
        )
        is None
    )


def _fake_clip(case_id, persona, text, seed=0):
    return Path("fake.wav"), 5.0


def test_billable_mode_refuses_without_confirmation_and_over_cap(
    monkeypatch, capsys, tmp_path
):
    def no_network(*args, **kwargs):
        raise AssertionError("network must not be used")

    monkeypatch.setattr(httpx, "post", no_network)
    monkeypatch.setattr(audio, "ensure_clip", _fake_clip)
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key-not-real")
    base = ["--mode", "deepgram", "--runs-dir", str(tmp_path)]
    assert run.main(base) == 2
    out = capsys.readouterr().out
    assert "Billable: 102 simulations, 510.0 s" in out and "Refusing" in out
    assert run.main([*base, "--confirm-billable", "--max-audio-seconds", "60"]) == 2
    assert "exceeds --max-audio-seconds" in capsys.readouterr().out
    assert not list(tmp_path.glob("*.json"))


def test_baseline_diff_flags_cases_that_got_worse(tmp_path):
    _, record = _mock_run(tmp_path / "first")
    for r in record["results"]:
        if r["metrics"]["safety_outcome"] == "flagged":
            r["metrics"]["safety_outcome"] = "exact"  # pretend it used to be better
            break
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(record))
    assert (
        run.main(["--runs-dir", str(tmp_path / "second"), "--baseline", str(baseline)])
        == 1
    )
    second = json.loads(next((tmp_path / "second").glob("*.json")).read_text())
    assert len(second["regressions"]) == 1
    assert second["regressions"][0]["before"] == "exact"


def test_deepgram_params_match_the_live_mic_adapter():
    menu = run.load_menu(run.MENU_PATH)
    # WAV has its own format header; the browser streams raw PCM16 instead.
    skip = ("keyterm", "interim_results", "encoding", "sample_rate", "channels")
    live = dict(
        p for p in parse_qsl(urlsplit(listen_url(menu)).query) if p[0] not in skip
    )
    harness = dict(p for p in run.deepgram_params(menu) if p[0] != "keyterm")
    assert harness == live
    assert harness["smart_format"] == "false" and harness["mip_opt_out"] == "true"
    assert harness["redact_usage"] == "true"


def test_personas_and_test_sets_are_well_formed():
    personas = run.load_personas()
    wanted = {
        "standard_server",
        "rushed_server",
        "line_cook_noise",
        "interrupted",
        "accented",
        "phone_quality",
    }
    assert wanted <= set(personas)
    fields = {"say_voice", "rate_wpm", "background", "snr_db", "overlap", "sample_rate"}
    assert all(fields <= set(p) for p in personas.values())
    sets = run.load_test_sets()
    assert all(
        case["utterance"] and case["expected_any"]
        for s in sets.values()
        for case in s["cases"]
    )


@pytest.mark.parametrize("persona_id", ["standard_server", "phone_quality"])
def test_clip_cache_key_changes_with_persona_and_text(persona_id):
    persona = run.load_personas()[persona_id]
    a = audio.clip_path("case", persona, "Heard, table four")
    b = audio.clip_path("case", persona, "Heard, table five")
    assert a != b and a.parent.name == persona_id


@pytest.mark.parametrize("cap", ["nan", "inf", "-inf", "0", "-1"])
def test_invalid_audio_caps_fail_before_rendering_or_spending(monkeypatch, cap):
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid caps must fail before work")

    monkeypatch.setattr(audio, "ensure_clip", forbidden)
    monkeypatch.setattr(httpx, "post", forbidden)
    with pytest.raises(SystemExit) as error:
        run.main(
            ["--mode", "deepgram", "--confirm-billable", "--max-audio-seconds", cap]
        )
    assert error.value.code == 2


def test_fractional_audio_above_cap_is_not_rounded_into_approval(monkeypatch, tmp_path):
    def no_network(*args, **kwargs):
        raise AssertionError("over-cap audio must not be sent")

    monkeypatch.setattr(httpx, "post", no_network)
    monkeypatch.setattr(audio, "ensure_clip", lambda *args: (Path("fake.wav"), 5.0004))
    count = len(run.load_test_sets()["server_orders"]["cases"])
    assert (
        run.main(
            [
                "--mode",
                "deepgram",
                "--test-set",
                "server_orders",
                "--persona",
                "standard_server",
                "--confirm-billable",
                "--max-audio-seconds",
                str(5 * count),
                "--runs-dir",
                str(tmp_path),
            ]
        )
        == 2
    )
    assert not list(tmp_path.glob("*.json"))


def test_clip_duration_preserves_sample_precision_and_cache_uses_repo_root(
    monkeypatch, tmp_path
):
    path = tmp_path / "cached.wav"
    path.touch()
    monkeypatch.setattr(audio, "clip_path", lambda *args: path)
    monkeypatch.setattr(
        audio.sf,
        "info",
        lambda _: SimpleNamespace(frames=81, samplerate=16000, channels=1),
    )
    monkeypatch.setattr(
        audio.sf, "read", lambda *a, **k: (np.ones(81, dtype="float32"), 16000)
    )
    _, duration = audio.ensure_clip("case", {}, "synthetic")
    assert duration == 81 / 16000
    assert audio.GENERATED == run.BACKEND.parent / "audio-samples/dig-in/generated"


def _kitchen_case():
    return {
        "id": "confidence",
        "flow": "kitchen",
        "utterance": "Heard table one",
        "context": [
            {
                "label": "T1",
                "table_id": "1",
                "state": "submitted",
                "lines": [{"menu_id": "the_bulldozer", "quantity": 1}],
            }
        ],
        "expected_any": [{"acknowledged": ["T1"], "started": []}],
    }


@pytest.mark.parametrize("confidence", [None, 0.2])
def test_live_confidence_reaches_both_real_domain_flows_and_restores_environment(
    monkeypatch, confidence
):
    monkeypatch.setenv("DIG_IN_VOICE_LIVE", "0")
    monkeypatch.setenv("DIG_IN_REQUIRE_DIETARY_CHECK", "1")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "synthetic-preserved-key")
    monkeypatch.setenv("DIG_IN_EMBEDDINGS_PROVIDER", "openai")
    menu = run.load_menu(run.MENU_PATH)
    kitchen = simulate.observe(
        _kitchen_case(), "Heard table one", menu, live=True, confidence=confidence
    )
    assert kitchen["acknowledged"] == [] and kitchen["asked"]
    server = simulate.observe(
        {"flow": "server", "selected_table_id": "1"},
        "Table one one bulldozer",
        menu,
        live=True,
        confidence=confidence,
    )
    assert "low_confidence" in server["flag_codes"]
    assert os.environ["DIG_IN_VOICE_LIVE"] == "0"
    assert os.environ["DIG_IN_REQUIRE_DIETARY_CHECK"] == "1"
    assert os.environ["DEEPGRAM_API_KEY"] == "synthetic-preserved-key"
    typed = simulate.observe(_kitchen_case(), "Heard table one", menu)
    assert typed["acknowledged"] == ["T1"] and not typed["asked"]


def test_simulation_restores_environment_when_domain_setup_fails(monkeypatch):
    monkeypatch.delenv("DIG_IN_VOICE_LIVE", raising=False)
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)

    def fail(_):
        raise ValueError("synthetic setup failure")

    monkeypatch.setattr(simulate, "_restaurant", fail)
    with pytest.raises(ValueError, match="setup failure"):
        simulate.observe(
            _kitchen_case(), "Heard table one", None, live=True, confidence=0.9
        )
    assert (
        "DIG_IN_VOICE_LIVE" not in os.environ and "DEEPGRAM_API_KEY" not in os.environ
    )


@pytest.mark.parametrize(
    "words, expected",
    [
        ([{"confidence": 0.99}, {"confidence": 0.1}, {"confidence": 0.99}], 0.1),
        ([{"confidence": 0.99}, {}], None),
        ([], None),
    ],
)
def test_prerecorded_confidence_uses_streaming_rule(
    monkeypatch, tmp_path, words, expected
):
    path = tmp_path / "synthetic.wav"
    path.write_bytes(b"synthetic-test-only")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "synthetic-key")

    def respond(url, **kwargs):
        assert dict(parse_qsl(urlsplit(url).query))["redact_usage"] == "true"
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {"transcript": "Heard table one", "words": words}
                            ]
                        }
                    ]
                }
            },
        )

    monkeypatch.setattr(httpx, "post", respond)
    heard, latency, confidence = run.transcribe(path, run.load_menu(run.MENU_PATH))
    assert heard == "Heard table one" and latency >= 0 and confidence == expected


def test_paid_runner_simulation_preserves_low_provider_confidence(monkeypatch):
    monkeypatch.setattr(run, "transcribe", lambda *args: ("Heard table one", 12, 0.1))
    sims = [
        {
            "test_set": "test",
            "case": _kitchen_case(),
            "persona": "synthetic",
            "iteration": 0,
            "source": "audio",
            "audio_path": "unused.wav",
        }
    ]
    result = run.simulate_all(sims, run.load_menu(run.MENU_PATH))[0]
    assert result["capture_mode"] == "live_voice" and result["stt_confidence"] == 0.1
    assert result["actual"]["asked"] and not result["actual"]["acknowledged"]
    assert result["metrics"]["safety_outcome"] == "flagged"


def test_duplicate_physical_unit_starts_are_not_collapsed():
    state = SimpleNamespace(
        orders={},
        dishes={
            "d1": SimpleNamespace(
                id="d1", order_id="o", menu_id="the_bulldozer", started_at=True
            ),
            "d2": SimpleNamespace(
                id="d2", order_id="o", menu_id="the_bulldozer", started_at=True
            ),
        },
    )
    _, starts = simulate._effects(SimpleNamespace(state=state), {"o": "T1"})
    actual = {"acknowledged": [], "started": sorted(starts.values()), "asked": False}
    expected = {"acknowledged": [], "started": ["T1:the_bulldozer"]}
    case = {"flow": "kitchen", "expected_any": [expected]}
    assert metrics.best_expected(case, actual)[1] is False
    assert metrics.outcome("kitchen", actual, False) == "wrong"
    assert metrics.item_precision(case, actual, expected, {}) == 0.5


@pytest.mark.parametrize(
    "samples",
    [np.array([], dtype="float32"), np.array([float("nan")], dtype="float32")],
)
def test_invalid_rendered_samples_fail_without_cache_or_spend(
    monkeypatch, tmp_path, samples
):
    monkeypatch.setattr(audio, "_say", lambda *a: samples)
    monkeypatch.setattr(audio, "clip_path", lambda *a: tmp_path / "synthetic.wav")
    with pytest.raises(ValueError, match="empty, nonfinite"):
        audio.ensure_clip(
            "case", run.load_personas()["standard_server"], "Heard table one"
        )
    assert not (tmp_path / "synthetic.wav").exists()


def test_header_only_cached_wav_fails_before_billable_requests(monkeypatch, tmp_path):
    path = tmp_path / "empty.wav"
    audio.sf.write(path, np.array([], dtype="float32"), 16000, subtype="PCM_16")
    monkeypatch.setattr(audio, "clip_path", lambda *a: path)

    def no_network(*args, **kwargs):
        raise AssertionError("invalid cache must not be sent")

    monkeypatch.setattr(httpx, "post", no_network)
    with pytest.raises(ValueError, match="Invalid cached synthetic clip"):
        run.main(
            [
                "--mode",
                "deepgram",
                "--test-set",
                "server_orders",
                "--persona",
                "standard_server",
                "--confirm-billable",
            ]
        )


def test_zero_duration_cannot_be_counted_as_free_audio(monkeypatch):
    monkeypatch.setattr(audio, "ensure_clip", lambda *a: (Path("fake.wav"), 0.0))
    sims = [
        {
            "source": "audio",
            "case": {"id": "test", "utterance": "synthetic"},
            "persona": "test",
        }
    ]
    with pytest.raises(ValueError, match="Invalid generated audio duration"):
        run.billable_seconds(sims, {"test": {}})
