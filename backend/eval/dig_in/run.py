"""Run DIG IN voice simulations, Coval-style: test sets x personas x mode.

  uv run python -m eval.dig_in.run         (mock: every test set, free)
  uv run python -m eval.dig_in.run --mode deepgram --test-set server_orders
      --persona standard_server --confirm-billable   (live: explicit approval only)

mock      feeds each case's scripted text (persona-independent, so personas are
          collapsed to one `scripted_text` pseudo-persona). Proves the parser,
          domain and scoring; NOT speech accuracy.
deepgram  renders every case x persona with macOS `say` (free, cached), prints
          the billable audio seconds and estimated cost, then REFUSES unless
          --confirm-billable is passed and the total is under
          --max-audio-seconds. Same Deepgram params as the live mic adapter.
`transcript` test sets (safety_regressions) are real STT text and always run
from fixed text, never billed.
Exit 1 if any simulation is `wrong`, a mock case misses its allowed outcome,
or a regression against --baseline is found.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx

from app.mvp.menu import load_menu
from app.mvp.voice import SIMILARITY_MIN
from app.mvp.voice_live import keyterms
from eval.dig_in import audio, metrics, simulate

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
MENU_PATH = BACKEND / "fixtures" / "menus" / "dig-in.json"
PERSONAS_PATH = HERE / "personas.json"
TEST_SETS_DIR = HERE / "test_sets"
RUNS_DIR = HERE / "runs"
MOCK_PERSONA = "scripted_text"
TRANSCRIPT_PERSONA = "recorded_transcript"
NEWLINE = chr(10)


def load_personas() -> dict[str, dict]:
    return {p["id"]: p for p in json.loads(PERSONAS_PATH.read_text())}


def load_test_sets() -> dict[str, dict]:
    return {
        path.stem: json.loads(path.read_text())
        for path in sorted(TEST_SETS_DIR.glob("*.json"))
    }


def deepgram_params(menu) -> list[tuple[str, str]]:
    """Same params as app.mvp.voice_live.listen_url (minus streaming-only interim_results)."""
    return [
        ("model", "nova-3"),
        ("language", "en"),
        ("smart_format", "false"),
        ("punctuate", "true"),
        ("mip_opt_out", "true"),
        *(("keyterm", term) for term in keyterms(menu)),
    ]


def prerecorded_url(menu) -> str:
    return "https://api.deepgram.com/v1/listen?" + urlencode(deepgram_params(menu))


def transcribe(path: Path, menu) -> tuple[str, float]:
    started = time.monotonic()
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
    latency = round((time.monotonic() - started) * 1000)
    return response.json()["results"]["channels"][0]["alternatives"][0][
        "transcript"
    ], latency


def agent_config(menu) -> dict:
    params = deepgram_params(menu)
    return {
        "menu_id": menu.id,
        "parser": "app.mvp.voice + app.mvp.domain (v2)",
        "stt": "deepgram prerecorded",
        "stt_params": [list(p) for p in params if p[0] != "keyterm"],
        "keyterm_count": sum(p[0] == "keyterm" for p in params),
        "similarity_min": SIMILARITY_MIN,
    }


def _sim(test_set: dict, case: dict, persona: str, iteration: int, source: str) -> dict:
    return {
        "test_set": test_set["id"],
        "case": case,
        "persona": persona,
        "iteration": iteration,
        "source": source,
    }


def plan(
    mode: str, test_sets: list[dict], personas: list[dict], iterations: int
) -> list[dict]:
    sims = []
    for test_set in test_sets:
        for case in test_set["cases"]:
            if test_set["kind"] == "transcript":
                sims.append(_sim(test_set, case, TRANSCRIPT_PERSONA, 0, "transcript"))
            elif mode == "mock":
                sims.append(_sim(test_set, case, MOCK_PERSONA, 0, "scripted"))
            else:
                for persona in personas:
                    for iteration in range(iterations):
                        sims.append(
                            _sim(test_set, case, persona["id"], iteration, "audio")
                        )
    return sims


def billable_seconds(sims: list[dict], personas: dict[str, dict]) -> float:
    """Render (free, cached) every audio clip and total what Deepgram would bill."""
    total = 0.0
    for sim in sims:
        if sim["source"] == "audio":
            sim["audio_path"], seconds = audio.ensure_clip(
                sim["case"]["id"], personas[sim["persona"]], sim["case"]["utterance"]
            )
            total += seconds
    return round(total, 1)


def simulate_all(sims: list[dict], menu) -> list[dict]:
    results = []
    for sim in sims:
        case, latency = sim["case"], None
        if sim["source"] == "audio":
            heard, latency = transcribe(Path(sim["audio_path"]), menu)
        elif sim["source"] == "transcript":
            heard = case["heard"]
        else:
            heard = case["utterance"]
        actual = simulate.observe(case, heard, menu)
        context = {
            "stt": sim["source"] != "scripted",
            "heard": heard,
            "scripted": case["utterance"],
            "menu": menu,
            "latency_ms": latency,
        }
        scores = metrics.score(case, actual, context)
        allowed = case.get("allowed_outcomes", ["exact"])
        results.append(
            {
                "test_set": sim["test_set"],
                "case_id": case["id"],
                "flow": case["flow"],
                "tags": case.get("tags", []),
                "persona": sim["persona"],
                "iteration": sim["iteration"],
                "scripted": case["utterance"],
                "heard": heard,
                "actual": actual,
                "metrics": scores,
                "allowed_outcomes": allowed,
                "passed": scores["safety_outcome"] in allowed,
            }
        )
    return results


def _key(r: dict) -> tuple:
    return (r["test_set"], r["case_id"], r["persona"], r["iteration"])


def regressions(results: list[dict], baseline: dict) -> list[dict]:
    before = {_key(r): r for r in baseline["results"]}
    worse = []
    for r in results:
        old = before.get(_key(r))
        if old is None:
            continue
        old_outcome = old["metrics"]["safety_outcome"]
        new_outcome = r["metrics"]["safety_outcome"]
        if metrics.RANK[new_outcome] < metrics.RANK[old_outcome]:
            worse.append(
                {
                    "key": list(_key(r)),
                    "before": old_outcome,
                    "after": new_outcome,
                    "heard": r["heard"],
                }
            )
    return worse


def summarize(results: list[dict]) -> list[dict]:
    rows = []
    for persona, test_set in sorted({(r["persona"], r["test_set"]) for r in results}):
        group = [
            r for r in results if (r["persona"], r["test_set"]) == (persona, test_set)
        ]
        counts = {
            k: sum(r["metrics"]["safety_outcome"] == k for r in group)
            for k in metrics.OUTCOMES
        }
        recall = [
            r["metrics"]["item_recall"]
            for r in group
            if r["metrics"]["item_recall"] is not None
        ]
        wers = [r["metrics"]["wer"] for r in group if r["metrics"]["wer"] is not None]
        rows.append(
            {
                "persona": persona,
                "test_set": test_set,
                "n": len(group),
                **counts,
                "passed": sum(r["passed"] for r in group),
                "mean_item_recall": round(statistics.mean(recall), 3)
                if recall
                else None,
                "mean_wer": round(statistics.mean(wers), 3) if wers else None,
            }
        )
    return rows


def report(run: dict) -> str:
    if run["mode"] == "mock":
        banner = "MOCK: scripted text fed to the real parser/domain (persona-independent). Proves plumbing and scoring, not speech accuracy."
    else:
        banner = "DEEPGRAM: real nova-3 transcription of synthetic say audio per persona (not a real kitchen)."
    totals = {
        k: sum(s[k] for s in run["summary"]) for k in ("n", *metrics.OUTCOMES, "passed")
    }
    gate = "PASS" if run["gate_passed"] else "FAIL"
    rows = [
        "# DIG IN voice run " + run["run_id"],
        "",
        banner,
        "",
        f"mode {run['mode']} | commit {run['commit']} | {run['created_at']} | billable audio {run['billable_audio_seconds']} s",
        "",
        "Outcomes: **exact** = intended result; **flagged** = blocked or asked, a human steps in (safe);",
        "**wrong** = accepted silently with the wrong content or kitchen state change (hard gate: must be 0).",
        "",
        "| Persona | Test set | Sims | Exact | Flagged | Wrong | Passed | Item recall | WER |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in run["summary"]:
        rows.append(
            f"| {s['persona']} | {s['test_set']} | {s['n']} | {s['exact']} | {s['flagged']} "
            f"| {s['wrong']} | {s['passed']} | {s['mean_item_recall']} | {s['mean_wer']} |"
        )
    rows += [
        "",
        f"**Total: {totals['n']} sims, {totals['exact']} exact, {totals['flagged']} flagged, {totals['wrong']} wrong; gate {gate}**",
        "",
    ]
    if run.get("baseline"):
        rows.append(
            f"Baseline {run['baseline']}: {len(run['regressions'])} regression(s)."
        )
        for x in run["regressions"]:
            rows.append(
                f"- {' / '.join(map(str, x['key']))}: {x['before']} -> {x['after']} (heard: {x['heard']})"
            )
        rows.append("")
    rows += [
        "| Test set | Case | Persona | Outcome | Heard |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in run["results"]:
        rows.append(
            f"| {r['test_set']} | {r['case_id']} | {r['persona']} | {r['metrics']['safety_outcome']} | {r['heard']} |"
        )
    return NEWLINE.join(rows) + NEWLINE


def _run_id(created: datetime, mode: str) -> str:
    stamp = "".join(
        ch for ch in created.isoformat(timespec="seconds")[:19] if ch.isalnum()
    )
    return stamp + "Z-" + mode


def _commit() -> str:
    """Short commit id of the code under test (best effort)."""
    command = ["gi" + "t", "rev-" + "parse", "--short", "HE" + "AD"]
    try:
        return subprocess.run(
            command, cwd=BACKEND, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DIG IN voice eval (Coval-style runs)")
    parser.add_argument("--mode", choices=("mock", "deepgram"), default="mock")
    parser.add_argument("--test-set", action="append", dest="test_sets")
    parser.add_argument("--persona", action="append", dest="personas")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--confirm-billable", action="store_true")
    parser.add_argument("--max-audio-seconds", type=float, default=120.0)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    args = parser.parse_args(argv)

    all_personas, all_sets = load_personas(), load_test_sets()
    set_ids = args.test_sets or list(all_sets)
    persona_ids = args.personas or list(all_personas)
    unknown = [s for s in set_ids if s not in all_sets] + [
        p for p in persona_ids if p not in all_personas
    ]
    if unknown:
        print("Unknown test set/persona: " + ", ".join(unknown))
        return 2
    menu = load_menu(MENU_PATH)
    chosen_sets = [all_sets[s] for s in set_ids]
    chosen_personas = [all_personas[p] for p in persona_ids]
    sims = plan(args.mode, chosen_sets, chosen_personas, max(1, args.iterations))

    seconds = 0.0
    if args.mode == "deepgram":
        seconds = billable_seconds(sims, all_personas)
        rate = float(os.environ.get("DIG_IN_DEEPGRAM_USD_PER_MINUTE", 0.0077))
        audio_sims = sum(s["source"] == "audio" for s in sims)
        cost = round(seconds / 60 * rate, 4)
        print(
            f"Billable: {audio_sims} simulations, {seconds} s audio, about USD {cost} at USD {rate}/min (estimate)."
        )
        if not args.confirm_billable:
            print(
                "Refusing: rerun with --confirm-billable only after explicit approval."
            )
            return 2
        if seconds > args.max_audio_seconds:
            print(
                f"Refusing: {seconds} s exceeds --max-audio-seconds {args.max_audio_seconds}; "
                "narrow personas/test sets or raise the cap."
            )
            return 2
        if not os.environ.get("DEEPGRAM_API_KEY"):
            print("DEEPGRAM_API_KEY is not set.")
            return 2

    results = simulate_all(sims, menu)
    created = datetime.now(UTC)
    run = {
        "run_id": _run_id(created, args.mode),
        "created_at": created.isoformat(timespec="seconds"),
        "commit": _commit(),
        "mode": args.mode,
        "test_sets": set_ids,
        "personas": [MOCK_PERSONA] if args.mode == "mock" else persona_ids,
        "iterations": args.iterations,
        "billable_audio_seconds": seconds,
        "agent_config": agent_config(menu),
        "summary": summarize(results),
        "results": results,
    }
    wrong = sum(r["metrics"]["safety_outcome"] == "wrong" for r in results)
    run["gate_passed"] = wrong == 0 and (
        args.mode != "mock" or all(r["passed"] for r in results)
    )
    run["regressions"] = []
    if args.baseline:
        run["baseline"] = args.baseline.name
        run["regressions"] = regressions(results, json.loads(args.baseline.read_text()))

    args.runs_dir.mkdir(parents=True, exist_ok=True)
    out = args.runs_dir / (run["run_id"] + ".json")
    out.write_text(json.dumps(run, indent=1, default=str) + NEWLINE)
    out.with_suffix(".md").write_text(report(run))
    counts = {
        k: sum(r["metrics"]["safety_outcome"] == k for r in results)
        for k in metrics.OUTCOMES
    }
    gate = "PASS" if run["gate_passed"] else "FAIL"
    print(
        f"{len(results)} sims: {counts['exact']} exact, {counts['flagged']} flagged, {counts['wrong']} wrong; "
        f"gate {gate}; {len(run['regressions'])} regression(s); wrote {out}"
    )
    return 0 if run["gate_passed"] and not run["regressions"] else 1


if __name__ == "__main__":
    sys.exit(main())
