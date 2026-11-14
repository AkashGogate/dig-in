"""Coval-style DIG IN voice harness: CI-safe (no network, no `say`, no spend)."""

import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest

from app.mvp.voice_live import listen_url
from eval.dig_in import audio, metrics, run, simulate


def _mock_run(tmp_path, *extra):
    code = run.main(["--runs-dir", str(tmp_path), *extra])
    record = json.loads(next(tmp_path.glob("*.json")).read_text())
    return code, record


def test_mock_run_covers_both_flows_with_zero_wrong(tmp_path):
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
    assert len(record["results"]) == 7
    for r in record["results"]:
        assert r["metrics"]["safety_outcome"] in ("exact", "flagged"), r["heard"]
        assert r["metrics"]["wer"] is not None  # real STT text, so WER is meaningful


def test_kitchen_wrong_means_a_real_wrong_state_change():
    menu = run.load_menu(run.MENU_PATH)
    case = {
        "flow": "kitchen",
        "utterance": "Heard, table four",
        "context": [
            {
                "label": "T1",
                "table_id": "1",
                "lines": [{"menu_id": "backhoe", "quantity": 1}],
                "state": "submitted",
            },
            {
                "label": "T4",
                "table_id": "4",
                "lines": [{"menu_id": "bulldozer", "quantity": 1}],
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
    line = {"menu_id": "bulldozer", "quantity": 2, "modifiers": []}
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
    skip = ("keyterm", "interim_results")
    live = dict(
        p for p in parse_qsl(urlsplit(listen_url(menu)).query) if p[0] not in skip
    )
    harness = dict(p for p in run.deepgram_params(menu) if p[0] != "keyterm")
    assert harness == live
    assert harness["smart_format"] == "false" and harness["mip_opt_out"] == "true"


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
