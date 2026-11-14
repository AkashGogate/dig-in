"""Fail CI on tracked local files or populated credential example templates.

This checks filenames/ignore behavior, not secret validity. Run a separate secret
scanner on the exact candidate tree/history before release; never print values.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path


def main():
    root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    )
    paths = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
        .decode()
        .split("\0")
    )
    failures = []
    ignored_tracked = subprocess.check_output(
        ["git", "ls-files", "-ci", "--exclude-standard"], cwd=root, text=True
    ).splitlines()
    failures.extend(
        f"Ignored local file is tracked: {name}" for name in ignored_tracked
    )
    directories = {
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".aws",
        ".ssh",
        "outputs",
        "captures",
        "recordings",
    }
    patterns = (
        ".DS_Store",
        "*.pyc",
        "*.db",
        "*.db-*",
        "*.sqlite*",
        "*.log",
        "*.pem",
        "*.key",
        "*.p12",
        "*.pfx",
        "credentials.json",
        "service-account*.json",
        ".envrc",
    )
    for name in filter(None, paths):
        path = Path(name)
        template = path.name.endswith(".env.example")
        forbidden_env = (
            path.name == ".env" or ".env." in path.name or path.name.endswith(".env")
        ) and not template
        if (
            forbidden_env
            or any(
                part in directories or part.startswith(".venv") for part in path.parts
            )
            or any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns)
        ):
            failures.append(f"Local/credential/generated file is tracked: {name}")
        if template:
            for number, line in enumerate((root / path).read_text().splitlines(), 1):
                match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
                if (
                    match
                    and re.search(
                        r"KEY|TOKEN|PASSWORD|SECRET|AUTH_PASS", match[1], re.I
                    )
                    and match[2].strip("\"'")
                ):
                    failures.append(
                        f"Credential example must be blank: {name}:{number}"
                    )
    ignored = [
        ".env",
        "backend/.env",
        "backend/.env.production",
        "local.env",
        "secrets.env.local",
        "backend/.venv/cache",
        "node_modules/pkg/index.js",
        "backend/state.db",
        "backend/state.sqlite3",
        "run.log",
        "capture.jsonl",
        "captures/menu.png",
        "private.pem",
        ".DS_Store",
    ]
    for name in ignored:
        if (
            subprocess.run(
                ["git", "check-ignore", "--no-index", "-q", name], cwd=root
            ).returncode
            != 0
        ):
            failures.append(f"Ignore protection missing: {name}")
    for name in [
        ".env.example",
        "backend/.env.example",
        "analytics/.env.example",
        "backend/fixtures/analytics/ten_scripted_orders.jsonl",
    ]:
        if (
            subprocess.run(
                ["git", "check-ignore", "--no-index", "-q", name], cwd=root
            ).returncode
            == 0
        ):
            failures.append(f"Portable example/fixture incorrectly ignored: {name}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(
        f"Repository hygiene passed: {len(list(filter(None, paths)))} indexed paths; credential examples blank; ignore probes passed."
    )


if __name__ == "__main__":
    main()
