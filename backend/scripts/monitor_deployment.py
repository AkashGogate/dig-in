"""Bounded read-only deployment checks; credentials come only from environment.

No order writes, capture, STT/OCR or paid calls. Each HTTP check inherits the
smoke probe's 15s timeout; attempts run sequentially, never concurrent workers.
Only sanitized check outcomes are printed; secrets/response bodies are omitted.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from scripts import smoke_deployment


def validate_bounds(attempts, interval_seconds):
    if (
        isinstance(attempts, bool)
        or not isinstance(attempts, int)
        or not 1 <= attempts <= 10
    ):
        raise ValueError("attempts must be an integer from 1 through 10")
    if not math.isfinite(interval_seconds) or not 0 <= interval_seconds <= 60:
        raise ValueError("interval-seconds must be finite and between 0 and 60")


def monitor(
    frontend,
    backend,
    require_live=False,
    *,
    attempts=5,
    interval_seconds=30,
    probe_fn=None,
    sleep_fn=None,
):
    """Poll until healthy or exhausted, with injectable reads/waits for tests."""
    validate_bounds(attempts, interval_seconds)
    report = {"passed": False, "attempts": []}
    # A missing/partial environment cannot become healthy by retrying public URLs.
    if not os.getenv("DEMO_AUTH_USER") or not os.getenv("DEMO_AUTH_PASS"):
        return {**report, "error": "credential_environment_unavailable"}
    read = smoke_deployment.probe if probe_fn is None else probe_fn
    wait = time.sleep if sleep_fn is None else sleep_fn
    for number in range(1, attempts + 1):
        try:
            outcome = read(frontend, backend, require_live)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # Exceptions can contain URLs/auth/body excerpts. Never stringify.
            outcome = {"passed": False, "checks": [], "error": "probe_failed"}
        report["attempts"].append({"attempt": number, **outcome})
        if outcome["passed"]:
            report["passed"] = True
            break
        if number < attempts:
            wait(interval_seconds)
    return report


def report_destination(value):
    """Allow temporary artifacts or Git-ignored paths, never tracked source."""
    path = Path(value).expanduser().resolve()
    root = Path(__file__).resolve().parents[2]
    if path.is_relative_to(root):
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", str(path)],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if ignored.returncode == 0:
            return path
    else:
        artifact_roots = [Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()]
        runner_temp = os.getenv("RUNNER_TEMP")
        if runner_temp:
            candidate = Path(runner_temp)
            # GitHub's runner temp lives outside /tmp. Trust only an absolute,
            # non-filesystem-root environment directory; repo paths still went
            # through the tracked/ignored guard above before this branch.
            if candidate.is_absolute() and candidate.resolve() != Path(
                candidate.anchor
            ):
                artifact_roots.append(candidate.resolve())
        if any(path.is_relative_to(root) for root in artifact_roots):
            return path
    raise argparse.ArgumentTypeError(
        "report-file must be a temporary or Git-ignored artifact"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", default=smoke_deployment.DEFAULT_FRONTEND)
    parser.add_argument("--backend", default=smoke_deployment.DEFAULT_BACKEND)
    parser.add_argument("--require-live-voice", action="store_true")
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--interval-seconds", type=float, default=30)
    parser.add_argument("--report-file", type=report_destination)
    args = parser.parse_args(argv)
    try:
        validate_bounds(args.attempts, args.interval_seconds)
    except ValueError as exc:
        parser.error(str(exc))
    report = monitor(
        args.frontend,
        args.backend,
        args.require_live_voice,
        attempts=args.attempts,
        interval_seconds=args.interval_seconds,
    )
    if args.report_file is not None:
        try:
            args.report_file.parent.mkdir(parents=True, exist_ok=True)
            args.report_file.write_text(json.dumps(report, indent=2) + "\n")
        except OSError:
            report = {**report, "passed": False, "error": "report_write_failed"}
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
