"""Retry a portable canonical JSONL batch to a fake or local JSONL sink.

The operational backend can call Outbox.drain from a worker; it must not call it
inside order requests. This CLI is a standalone interface demonstration only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.analytics.analyze import load
from app.analytics.outbox import FakeAdapter, JsonlAdapter, Outbox


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--jsonl-output", type=Path)
    parser.add_argument("--simulate-failures", type=int, default=0)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()
    outbox = Outbox()
    outbox.enqueue(load(args.input))
    adapter = (
        JsonlAdapter(args.jsonl_output)
        if args.jsonl_output
        else FakeAdapter(args.simulate_failures)
    )
    for _ in range(args.attempts):
        health = outbox.drain(adapter)
        attempts = health.pop("pending_attempts")
        health["max_pending_attempts"] = max(attempts.values(), default=0)
        print(json.dumps(health, sort_keys=True))
        if not outbox.health()["pending"]:
            break
    if outbox.health()["pending"]:
        raise SystemExit(
            "Pending rows retained in this running outbox, but CLI exit loses in-memory state; rerun the same input file to retry safely"
        )


if __name__ == "__main__":
    main()
