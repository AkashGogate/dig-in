"""Shared demo access gate. No credentials enter frontend assets or logs.

Both unset permits explicit local development only. Partial config or deployment
without credentials fails closed. Voice WebSockets use their single-use ticket;
all HTTP application surfaces are covered by DemoAccessMiddleware.
"""

from __future__ import annotations

import base64
import binascii
import os
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

_basic_auth = HTTPBasic(auto_error=False)


def auth_required() -> bool:
    return bool(
        os.environ.get("DEMO_AUTH_USER")
        or os.environ.get("DEMO_AUTH_PASS")
        or os.environ.get("DIG_IN_REQUIRE_AUTH") == "1"
        or os.environ.get("FLY_APP_NAME")
    )


def valid_credentials(username: str, password: str) -> bool:
    user, secret = os.environ.get("DEMO_AUTH_USER"), os.environ.get("DEMO_AUTH_PASS")
    return bool(user and secret) and (
        secrets.compare_digest(username.encode(), user.encode())
        & secrets.compare_digest(password.encode(), secret.encode())
    )


def require_demo_auth(
    credentials: HTTPBasicCredentials | None = Depends(_basic_auth),
) -> None:
    if auth_required() and (
        credentials is None
        or not valid_credentials(credentials.username, credentials.password)
    ):
        raise HTTPException(
            status_code=401,
            detail="Demo sign-in required",
            headers={"WWW-Authenticate": 'Basic realm="Dig In demo"'},
        )


class DemoAccessMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        # Health is deliberately public/minimal. CORS preflight contains no data.
        if (
            scope["type"] != "http"
            or scope.get("method") == "OPTIONS"
            or scope.get("path") == "/healthz"
            or not auth_required()
        ):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        encoded = headers.get(b"authorization", b"").decode("ascii", errors="ignore")
        valid = False
        if encoded.lower().startswith("basic "):
            try:
                raw = base64.b64decode(encoded[6:], validate=True).decode("utf-8")
                username, password = raw.split(":", 1)
                valid = valid_credentials(username, password)
            except (ValueError, UnicodeError, binascii.Error):
                pass
        if not valid:
            response = JSONResponse(
                {"detail": "Demo sign-in required"},
                status_code=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="Dig In demo"',
                    "Cache-Control": "no-store",
                },
            )
            await response(scope, receive, send)
            return

        async def uncached(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != b"cache-control"
                ] + [(b"cache-control", b"no-store")]
            await send(message)

        await self.app(scope, receive, uncached)
