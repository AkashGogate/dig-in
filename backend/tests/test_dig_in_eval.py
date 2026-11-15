"""DIG IN voice eval plumbing: mock scoring is exact, billable mode never runs unasked."""

import httpx

from eval import run_dig_in_eval as dig_in


def test_mock_mode_scores_every_ground_truth_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(dig_in, "SCORECARD_PATH", tmp_path / "scorecard.md")
    results = dig_in.evaluate("mock")
    assert len(results) == 18
    assert {r["flow"] for r in results} == {"server", "kitchen"}
    assert {r["condition"] for r in results} == {"clean", "noise", "overlap"}
    assert [r["name"] for r in results if not r["passed"]] == []
    assert dig_in.main(["--mode", "mock"]) == 0
    assert "MOCK" in (tmp_path / "scorecard.md").read_text()


def test_scoring_catches_a_wrong_parse():
    menu = dig_in.load_menu(dig_in.MENU_PATH)
    clip = {"flow": "server", "selected_table_id": "4"}
    expected = {
        "table_id": "4",
        "lines": [{"menu_id": "bulldozer", "quantity": 2, "modifiers": []}],
        "flag_codes": [],
    }
    wrong = dig_in.observe(clip, "Table four, three bulldozers", menu)
    assert not dig_in.matches(expected, wrong)


def test_billable_mode_refuses_without_confirmation(monkeypatch, capsys):
    def no_network(*args, **kwargs):
        raise AssertionError("network must not be used")

    monkeypatch.setattr(httpx, "post", no_network)
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key-not-real")
    assert dig_in.main(["--mode", "deepgram"]) == 2
    out = capsys.readouterr().out
    assert "Billable" in out and "Refusing" in out


def test_deepgram_params_match_live_adapter():
    url = dig_in.prerecorded_url(dig_in.load_menu(dig_in.MENU_PATH))
    assert "model=nova-3" in url and "mip_opt_out=true" in url
    assert "keyterm=The+Bulldozer" in url and "diarize" not in url
