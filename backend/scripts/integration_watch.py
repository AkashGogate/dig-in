"""Cheap read-only remote-head comparison; no checkout, merge, build or paid API.

Run with --record only after triaging the observed revision set. Cache is ignored
local metadata; remote hashes are not readiness proof. Missing cache bootstraps a
baseline without pretending prior changes have been integrated.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--remote", default="origin")
    p.add_argument("--cache", type=Path, default=Path("outputs/integration-watch.json"))
    p.add_argument("--record", action="store_true")
    args = p.parse_args()
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", args.remote],
            capture_output=True,
            text=True,
            check=True,
            timeout=25,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        heads = {
            line.split()[1].removeprefix("refs/heads/"): line.split()[0]
            for line in result.stdout.splitlines()
        }
    except (OSError, subprocess.SubprocessError):
        raise SystemExit(
            "Remote branch check failed; no branch or cache was changed."
        ) from None
    before = json.loads(args.cache.read_text()) if args.cache.exists() else None
    changes = (
        []
        if before is None
        else [
            {"branch": b, "previous": before.get(b), "current": heads.get(b)}
            for b in sorted(heads.keys() | before.keys())
            if before.get(b) != heads.get(b)
        ]
    )
    if before is None or args.record:
        args.cache.parent.mkdir(parents=True, exist_ok=True)
        temp = args.cache.with_suffix(".tmp")
        temp.write_text(json.dumps(heads, sort_keys=True))
        temp.replace(args.cache)
    print(
        json.dumps(
            {
                "baseline_created": before is None,
                "changed": bool(changes),
                "changes": changes,
                "branch_count": len(heads),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
