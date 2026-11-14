"""DIG IN voice eval: Server orders and Kitchen callouts through the v2 parser.

Clips/ground truth come from audio_gen/generate_dig_in.py
(audio-samples/dig-in/manifest.json). Each clip is scored exactly against the
DIG IN menu: spoken table, lines (menu_id/quantity/modifiers), flag codes and
review candidates for Server orders; action/table/dish for Kitchen callouts.

  --mode mock      feeds the ground-truth transcript text (no audio, free).
                   Proves parser + scoring plumbing; NOT speech accuracy.
  --mode deepgram  transcribes each WAV with Deepgram prerecorded using the
                   same params as the live adapter (nova-3, en, punctuate, smart_format off,
                   mip_opt_out, menu keyterms). BILLABLE: refuses unless
                   --confirm-billable is passed, and prints the audio seconds
                   and estimated cost first. Run only with explicit approval.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import httpx

from app.mvp.menu import load_menu
from app.mvp.voice import parse_kitchen, parse_order
from app.mvp.voice_live import keyterms

BACKEND = Path(__file__).resolve().parents[1]
CORPUS = BACKEND.parent / "audio-samples" / "dig-in"
MANIFEST_PATH = CORPUS / "manifest.json"
SCORECARD_PATH = CORPUS / "scorecard.md"
MENU_PATH = BACKEND / "fixtures" / "menus" / "dig-in.json"
LINE_KEYS = ("menu_id", "quantity", "modifiers")
NEWLINE = chr(10)


def prerecorded_url(menu) -> str:
    params = [
        ("model", "nova-3"),
        ("language", "en"),
        (
            "smart_format",
            "false",
        ),  # live eval: smart_format merged "three, one backhoe" into "31"
        ("punctuate", "true"),
        ("mip_opt_out", "true"),
        *(("keyterm", term) for term in keyterms(menu)),
    ]
    return "https://api.deepgram.com/v1/listen?" + urlencode(params)


def transcribe(path: Path, menu) -> str:
    response = httpx.post(
        prerecorded_url(menu),
        headers={
            "Authorization": "Token " + os.environ["DEEPGRAM_API_KEY"],
            "Content-Type": "audio/wav",
        },
        content=path.read_bytes(),
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["results"]["channels"][0]["alternatives"][0]["transcript"]


def observe(clip: dict, text: str, menu) -> dict:
    if clip["flow"] == "kitchen":
        parsed = parse_kitchen(menu, text)
        return {k: parsed.get(k) for k in ("action", "table_id", "menu_id")}
    parsed = parse_order(menu, text, clip["selected_table_id"])
    return {
        "table_id": parsed["table_id"],
        "lines": [{k: line[k] for k in LINE_KEYS} for line in parsed["lines"]],
        "flag_codes": sorted(f["code"] for f in parsed["flags"]),
        "candidates": sorted(
            {c for f in parsed["flags"] for c in f.get("candidates", [])}
        ),
    }


def matches(expected: dict, actual: dict) -> bool:
    for key, want in expected.items():
        if key == "flag_codes":
            if sorted(want) != actual[key]:
                return False
        elif key == "candidates":
            if not set(want) <= set(actual[key]):
                return False
        elif actual.get(key) != want:
            return False
    return True


def outcome(flow: str, actual: dict, passed: bool) -> str:
    """exact | flagged (blocked or no action: a human must step in) | wrong (accepted silently)."""
    if passed:
        return "exact"
    if flow == "kitchen":
        return "flagged" if actual["action"] is None else "wrong"
    return "flagged" if actual["flag_codes"] else "wrong"


def evaluate(mode: str, manifest_path: Path = MANIFEST_PATH) -> list[dict]:
    menu = load_menu(MENU_PATH)
    results = []
    for clip in json.loads(manifest_path.read_text()):
        if mode == "mock":
            text = clip["transcript"]
        else:
            text = transcribe(manifest_path.parent / clip["file"], menu)
        actual = observe(clip, text, menu)
        passed = any(matches(e, actual) for e in clip["expected_any"])
        results.append(
            {
                "name": clip["name"],
                "flow": clip["flow"],
                "condition": clip["condition"],
                "heard": text,
                "actual": actual,
                "passed": passed,
                "outcome": outcome(clip["flow"], actual, passed),
            }
        )
    return results


def scorecard(mode: str, results: list[dict]) -> str:
    if mode == "mock":
        banner = "MOCK: ground-truth text fed to the parser. Proves plumbing/scoring, not speech accuracy."
    else:
        banner = "DEEPGRAM: real nova-3 transcription of synthetic say clips (not a real kitchen)."
    rows = ["# DIG IN voice eval scorecard (" + mode + ")", "", banner, ""]
    rows += [
        "Outcomes: **exact** = parsed as intended; **flagged** = blocked or no action, a human",
        "must review (safe); **wrong** = accepted silently with the wrong content (unsafe).",
        "",
        "| Flow | Condition | Exact | Flagged | Wrong |",
        "| --- | --- | --- | --- | --- |",
    ]
    count = lambda group, kind: sum(r["outcome"] == kind for r in group)  # noqa: E731
    for flow, condition in sorted({(r["flow"], r["condition"]) for r in results}):
        group = [r for r in results if (r["flow"], r["condition"]) == (flow, condition)]
        rows.append(
            f"| {flow} | {condition} | {count(group, 'exact')}/{len(group)} "
            f"| {count(group, 'flagged')} | {count(group, 'wrong')} |"
        )
    rows += [
        "",
        f"**Total: {count(results, 'exact')}/{len(results)} exact, "
        f"{count(results, 'flagged')} flagged, {count(results, 'wrong')} wrong**",
        "",
        "| Clip | Outcome | Heard |",
        "| --- | --- | --- |",
    ]
    for r in results:
        rows.append("| " + r["name"] + " | " + r["outcome"] + " | " + r["heard"] + " |")
    return NEWLINE.join(rows) + NEWLINE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DIG IN voice eval")
    parser.add_argument("--mode", choices=("mock", "deepgram"), default="mock")
    parser.add_argument("--confirm-billable", action="store_true")
    args = parser.parse_args(argv)
    if args.mode == "deepgram":
        clips = json.loads(MANIFEST_PATH.read_text())
        seconds = sum(c["seconds"] for c in clips)
        rate = float(os.environ.get("DIG_IN_DEEPGRAM_USD_PER_MINUTE", 0.0077))
        cost = seconds / 60 * rate
        print(
            f"Billable: {len(clips)} clips, {seconds:.1f}s audio, "
            f"~${cost:.4f} at ${rate}/min (estimate)."
        )
        if not args.confirm_billable:
            print(
                "Refusing: rerun with --confirm-billable only after explicit approval."
            )
            return 2
        if not os.environ.get("DEEPGRAM_API_KEY"):
            print("DEEPGRAM_API_KEY is not set.")
            return 2
    results = evaluate(args.mode)
    SCORECARD_PATH.write_text(scorecard(args.mode, results))
    kinds = {
        k: sum(r["outcome"] == k for r in results)
        for k in ("exact", "flagged", "wrong")
    }
    print(
        f"{kinds['exact']}/{len(results)} exact, {kinds['flagged']} flagged, "
        f"{kinds['wrong']} wrong ({args.mode}); wrote {SCORECARD_PATH}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
