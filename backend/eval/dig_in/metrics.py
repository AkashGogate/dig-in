"""Deterministic metrics. Each returns a value or None (not applicable).

Hard gate: no simulation may be `wrong` (accepted silently with the wrong
content / wrong kitchen state change). Accuracy metrics are reported, not gated.
"""

from __future__ import annotations

from collections import Counter

from app.mvp.menu import MenuDocument, names, normalize

OUTCOMES = ("exact", "flagged", "wrong")
RANK = {"exact": 2, "flagged": 1, "wrong": 0}


def matches(expected: dict, actual: dict) -> bool:
    for key, want in expected.items():
        if key == "lines":
            got = actual.get("lines", [])
            if len(got) != len(want):
                return False
            for exp_line, act_line in zip(want, got, strict=True):
                if any(act_line.get(k) != v for k, v in exp_line.items()):
                    return False
        elif key in ("flag_codes", "acknowledged", "started"):
            if sorted(want) != sorted(actual.get(key, [])):
                return False
        elif key == "candidates":
            if not set(want) <= set(actual.get(key, [])):
                return False
        elif actual.get(key) != want:
            return False
    return True


def best_expected(case: dict, actual: dict) -> tuple[dict, bool]:
    for expected in case["expected_any"]:
        if matches(expected, actual):
            return expected, True
    return case["expected_any"][0], False


def outcome(flow: str, actual: dict, passed: bool) -> str:
    """exact | flagged (blocked/asked: a human must step in) | wrong (silent)."""
    if passed:
        return "exact"
    if flow == "kitchen":
        changed = actual.get("acknowledged") or actual.get("started")
        return "wrong" if changed else "flagged"
    return "flagged" if actual.get("flag_codes") else "wrong"


def _units(lines: list[dict]) -> Counter:
    units = Counter()
    for line in lines:
        units[line["menu_id"]] += line.get("quantity", 1)
    return units


def _ratio(hits: int, total: int) -> float | None:
    return round(hits / total, 3) if total else None


def table_accuracy(case, actual, expected, sim):
    if case["flow"] != "server":
        return None
    return actual.get("table_id") == expected.get("table_id")


def item_precision(case, actual, expected, sim):
    if case["flow"] == "kitchen":
        got = Counter(actual["acknowledged"] + actual["started"])
        want = Counter(expected.get("acknowledged", []) + expected.get("started", []))
        return _ratio(sum((got & want).values()), sum(got.values()))
    got, want = _units(actual["lines"]), _units(expected.get("lines", []))
    return _ratio(sum((got & want).values()), sum(got.values()))


def item_recall(case, actual, expected, sim):
    if case["flow"] == "kitchen":
        got = Counter(actual["acknowledged"] + actual["started"])
        want = Counter(expected.get("acknowledged", []) + expected.get("started", []))
        return _ratio(sum((got & want).values()), sum(want.values()))
    got, want = _units(actual["lines"]), _units(expected.get("lines", []))
    return _ratio(sum((got & want).values()), sum(want.values()))


def _shared_lines(actual, expected):
    got = {line["menu_id"]: line for line in actual.get("lines", [])}
    return [
        (line, got[line["menu_id"]])
        for line in expected.get("lines", [])
        if line["menu_id"] in got
    ]


def quantity_accuracy(case, actual, expected, sim):
    if case["flow"] != "server":
        return None
    pairs = _shared_lines(actual, expected)
    return _ratio(sum(e["quantity"] == a["quantity"] for e, a in pairs), len(pairs))


def modifier_accuracy(case, actual, expected, sim):
    if case["flow"] != "server":
        return None
    pairs = _shared_lines(actual, expected)
    return _ratio(
        sum(sorted(e["modifiers"]) == sorted(a["modifiers"]) for e, a in pairs),
        len(pairs),
    )


def seat_dietary_capture(case, actual, expected, sim):
    if case["flow"] != "server":
        return None
    checks = [
        e[k] == a.get(k)
        for e, a in _shared_lines(actual, expected)
        for k in ("seat", "requests")
        if k in e
    ]
    if "dietary_check" in expected:
        checks.append(actual.get("dietary_check") == expected["dietary_check"])
    return _ratio(sum(checks), len(checks))


def flag_correctness(case, actual, expected, sim):
    if case["flow"] == "kitchen":
        should_ask = not (expected.get("acknowledged") or expected.get("started"))
        return actual["asked"] == should_ask
    if "flag_codes" not in expected:
        return None
    return sorted(actual["flag_codes"]) == sorted(expected["flag_codes"])


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference).split(), normalize(hypothesis).split()
    row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, row[0] = row[0], i
        for j, h in enumerate(hyp, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (r != h))
    return round(row[-1] / len(ref), 3) if ref else 0.0


def wer(case, actual, expected, sim):
    return word_error_rate(sim["scripted"], sim["heard"]) if sim["stt"] else None


def stt_latency_ms(case, actual, expected, sim):
    return sim.get("latency_ms") if sim["stt"] else None


def menu_term_hits(menu: MenuDocument, scripted: str, heard: str) -> float | None:
    said, got = f" {normalize(scripted)} ", f" {normalize(heard)} "
    terms = {
        alias
        for item in menu.items
        for entity in [item, *item.modifiers]
        for alias in names(entity)
        if f" {alias} " in said
    }
    # Count only the longest terms said, so "bulldozers" isn't also scored as "bulldozer".
    terms = {
        t for t in terms if not any(t != o and f" {t} " in f" {o} " for o in terms)
    }
    return _ratio(sum(f" {t} " in got for t in terms), len(terms))


def menu_term_hit_rate(case, actual, expected, sim):
    return (
        menu_term_hits(sim["menu"], sim["scripted"], sim["heard"])
        if sim["stt"]
        else None
    )


METRICS = {
    "table_accuracy": table_accuracy,
    "item_precision": item_precision,
    "item_recall": item_recall,
    "quantity_accuracy": quantity_accuracy,
    "modifier_accuracy": modifier_accuracy,
    "seat_dietary_capture": seat_dietary_capture,
    "flag_correctness": flag_correctness,
    "wer": wer,
    "stt_latency_ms": stt_latency_ms,
    "menu_term_hit_rate": menu_term_hit_rate,
}


def score(case: dict, actual: dict, sim: dict) -> dict:
    expected, passed = best_expected(case, actual)
    result = {
        "exact_parse": passed,
        "safety_outcome": outcome(case["flow"], actual, passed),
    }
    for name, fn in METRICS.items():
        result[name] = fn(case, actual, expected, sim)
    return result
