"""Read-only Fly/Vercel readiness probe; prints outcomes, never credentials/state.

Run after deployment with DEMO_AUTH_USER/PASS in the process environment. This
does not order food, record audio, invoke STT/OCR, or claim hardware validation.
Use the separately gated voice evaluator and opt-in CV runner for those checks.
"""

from __future__ import annotations

import argparse
import json
import os

import httpx


def valid_state(response):
    """An older v2 snapshot is not proof of this release's menu integration."""
    data = response.json()
    return (
        isinstance(data, dict)
        and data.get("schema_version") == 2
        and isinstance(data.get("menu_revision"), str)
        and bool(data["menu_revision"])
    )


def valid_voice(response, require_live):
    data = response.json()
    return (
        isinstance(data, dict)
        and isinstance(data.get("mode"), str)
        and data["mode"]
        in (
            {"deepgram_stream"}
            if require_live
            else {"mock_transcript", "deepgram_stream"}
        )
    )


DEFAULT_FRONTEND = "https://www.frictionless-kitchen.akashgogate.com"
DEFAULT_BACKEND = "https://api.frictionless-kitchen.akashgogate.com"


def probe(frontend, backend, require_live=False):
    """Return sanitized read-only outcomes; never print response bodies or auth."""
    results = []

    def check(name, url, expected=200, *, auth=None, validate=None):
        try:
            response = httpx.get(url, auth=auth, timeout=15, follow_redirects=False)
            passed = response.status_code == expected
            if validate and passed:
                passed = bool(validate(response))
            results.append(
                {"check": name, "passed": passed, "status": response.status_code}
            )
            return response if passed else None
        except (httpx.HTTPError, ValueError, KeyError):
            results.append(
                {"check": name, "passed": False, "error": "request_or_shape_failed"}
            )
            return None

    front, back = frontend.rstrip("/"), backend.rstrip("/")
    check(
        "public_minimal_health",
        back + "/healthz",
        validate=lambda r: r.json() == {"status": "ok", "schema_version": 2},
    )
    for name, url in [
        ("backend_requires_login", back + "/api/v2/state"),
        ("backend_contracts_require_login", back + "/openapi.json"),
        ("frontend_requires_login", front + "/"),
        ("frontend_asset_requires_login", front + "/config.js"),
        ("proxy_requires_login", front + "/api/v2/state"),
    ]:
        check(
            name,
            url,
            expected=401,
            validate=lambda r: r.headers.get("www-authenticate", "").startswith(
                "Basic "
            ),
        )
    user, password = os.getenv("DEMO_AUTH_USER"), os.getenv("DEMO_AUTH_PASS")
    if user and password:
        auth = httpx.BasicAuth(user, password)
        check(
            "frontend_login",
            front + "/",
            auth=auth,
            validate=lambda r: "text/html" in r.headers.get("content-type", ""),
        )
        state = check(
            "backend_login",
            back + "/api/v2/state",
            auth=auth,
            validate=valid_state,
        )
        proxy = check(
            "frontend_proxy",
            front + "/api/v2/state",
            auth=auth,
            validate=valid_state,
        )
        if state is not None and proxy is not None:
            results.append(
                {
                    "check": "shared_menu_revision",
                    "passed": state.json()["menu_revision"]
                    == proxy.json()["menu_revision"],
                }
            )
        check(
            "voice_mode",
            front + "/api/v2/voice/status",
            auth=auth,
            validate=lambda r: valid_voice(r, require_live),
        )
    else:
        results.append(
            {
                "check": "authenticated_checks",
                "passed": False,
                "error": "credential_environment_unavailable",
            }
        )
    return {"passed": all(r["passed"] for r in results), "checks": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", default=DEFAULT_FRONTEND)
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--require-live-voice", action="store_true")
    args = parser.parse_args()
    report = probe(args.frontend, args.backend, args.require_live_voice)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
