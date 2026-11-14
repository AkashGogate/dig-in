"""Shared demo password gate for Deepgram-billable endpoints (ARCHITECTURE.md #6 cost controls)."""

from __future__ import annotations

import os
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_basic_auth = HTTPBasic(auto_error=False)


def auth_required() -> bool:
    return bool(os.environ.get("DEMO_AUTH_USER") and os.environ.get("DEMO_AUTH_PASS"))


def require_demo_auth(
    credentials: HTTPBasicCredentials | None = Depends(_basic_auth),
) -> None:
    """No-op only when DEMO_AUTH_USER/PASS are both unset (local dev)."""
    if not auth_required():
        return
    ok = credentials is not None and (
        secrets.compare_digest(credentials.username, os.environ["DEMO_AUTH_USER"])
        & secrets.compare_digest(credentials.password, os.environ["DEMO_AUTH_PASS"])
    )
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
