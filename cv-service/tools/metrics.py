"""Compare events.jsonl to labels.jsonl (CV_SPEC.md section 12).

    python tools/metrics.py logs/replay_events.jsonl recordings/run1.labels.jsonl [--tol 2]

Events and labels must share a clock (use tools/replay.py on the clip recorded by
tools/label.py). Matches within +/- tol seconds. Prints a markdown table of measured
numbers only; anything that cannot be measured from the inputs is reported as n/a.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def ts(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def load(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def match(labels: list[dict], events: list[dict], tol: float, key) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """Greedy nearest-in-time matching on equal key(). Returns (pairs, missed_labels, false_events)."""
    used: set[int] = set()
    pairs, missed = [], []
    for lab in sorted(labels, key=lambda l: l["t"]):
        best, best_dt = None, tol + 1e-9
        for i, ev in enumerate(events):
            if i in used or key(ev) != (lab["target"]):
                continue
            dt = abs(ev["_t"] - lab["t"])
            if dt <= best_dt:
                best, best_dt = i, dt
        if best is None:
            missed.append(lab)
        else:
            used.add(best)
            pairs.append((lab, events[best]))
    false = [ev for i, ev in enumerate(events) if i not in used]
    return pairs, missed, false


def pct(a: int, b: int) -> str:
    return "n/a" if b == 0 else f"{100 * a / b:.0f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("events")
    ap.add_argument("labels")
    ap.add_argument("--tol", type=float, default=2.0)
    args = ap.parse_args()
    evs = load(args.events)
    for e in evs:
        e["_t"] = ts(e["observed_at"])
    labs = load(args.labels)
    rows: list[tuple[str, str, str]] = []

    # ---- plating ----
    for kind, etype, name in (("plate_in", "PLATE_ARRIVED", "arrivals"), ("plate_out", "PLATE_REMOVED", "removals")):
        L = [l for l in labs if l["kind"] == kind]
        E = [e for e in evs if e["type"] == etype]
        # one event may cover several plates (delta>1); expand by delta
        E = [e for e in E for _ in range(e["payload"]["delta"])]
        pairs, missed, false = match(L, E, args.tol, key=lambda e: e["bay_id"])
        if L or E:
            rows.append(("Plating", f"{name}: labelled / detected", f"{len(L)} / {len(E)}"))
            rows.append(("Plating", f"{name}: missed", f"{len(missed)} ({pct(len(missed), len(L))})"))
            rows.append(("Plating", f"{name}: false", str(len(false))))
    states = [e for e in evs if e["type"] == "BAY_STATE"]
    if states:
        # plate-count accuracy over time: compare each BAY_STATE to the label-derived count at that time
        truth: dict[str, list[tuple[float, int]]] = {}
        for l in sorted(labs, key=lambda l: l["t"]):
            if l["kind"] in ("plate_in", "plate_out"):
                cur = truth.setdefault(l["target"], [(0.0, 0)])
                cur.append((l["t"], cur[-1][1] + (1 if l["kind"] == "plate_in" else -1)))
        checked = correct = 0
        for s in states:
            series = truth.get(s["bay_id"], [(0.0, 0)])
            if any(abs(s["_t"] - t) <= args.tol for t, _ in series[1:]):
                continue  # skip samples inside a transition window
            expected = [c for t, c in series if t <= s["_t"]][-1]
            checked += 1
            correct += int(s["payload"]["plate_count"] == expected)
        rows.append(("Plating", "plate-count accuracy (BAY_STATE samples)", f"{pct(correct, checked)} of {checked}"))

    # ---- ingredient ----
    for kind, etype in (("pick", "INGREDIENT_PICKED"), ("return", "INGREDIENT_RETURNED")):
        L = [l for l in labs if l["kind"] == kind]
        E = [e for e in evs if e["type"] == etype]
        if not (L or E):
            continue
        pairs, missed, false = match(L, E, args.tol, key=lambda e: e["zone_id"])
        qty_err = sum(1 for l, e in pairs if abs(e["payload"]["qty_delta"]) != l.get("qty", 1))
        rows.append(("Ingredient", f"{kind}s: labelled / detected", f"{len(L)} / {len(E)}"))
        rows.append(("Ingredient", f"{kind}s: missed", f"{len(missed)} ({pct(len(missed), len(L))})"))
        rows.append(("Ingredient", f"{kind}s: false", str(len(false))))
        rows.append(("Ingredient", f"{kind}s: quantity errors", f"{qty_err} of {len(pairs)} matched"))
    ing = [e for e in evs if e["type"] in ("INGREDIENT_PICKED", "INGREDIENT_RETURNED", "INGREDIENT_CHANGE_PENDING")]
    if ing:
        pend = sum(1 for e in ing if e["type"] == "INGREDIENT_CHANGE_PENDING")
        rows.append(("Ingredient", "pending rate", f"{pct(pend, len(ing))} ({pend} of {len(ing)})"))
        labelled_with_ticket = [l for l in labs if l["kind"] == "pick" and l.get("ticket")]
        rows.append(("Ingredient", "correct attribution rate",
                     "n/a (labels carry no ticket)" if not labelled_with_ticket else "see labels"))

    # ---- health ----
    starts = [l["t"] for l in labs if l["kind"] == "obstruct_start"]
    ends = [l["t"] for l in labs if l["kind"] == "obstruct_end"]
    obs = [e for e in evs if e["type"] == "CAMERA_STATUS" and e["payload"]["state"] == "obstructed"
           and not e["payload"].get("heartbeat")]
    if starts or obs:
        lat = []
        for s in starts:
            after = [e["_t"] - s for e in obs if e["_t"] >= s - 0.5]
            if after:
                lat.append(min(after))
        windows = list(zip(starts, ends + [float("inf")] * (len(starts) - len(ends))))
        false = [e for e in obs if not any(a - args.tol <= e["_t"] <= b + args.tol for a, b in windows)]
        rows.append(("Health", "obstructions labelled / detected", f"{len(starts)} / {len(lat)}"))
        rows.append(("Health", "detection latency (mean / max)",
                     "n/a" if not lat else f"{sum(lat) / len(lat):.2f} s / {max(lat):.2f} s"))
        rows.append(("Health", "false obstruction triggers", str(len(false))))

    print("| Module | Metric | Value |\n|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | {r[1]} | {r[2]} |")
    if not rows:
        print("| - | nothing to compare | - |")


if __name__ == "__main__":
    main()
