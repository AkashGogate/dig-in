"""Deployment access gate covers data, commands and schema, not just paid STT."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.demo_auth import DemoAccessMiddleware


@pytest.fixture
def gated(monkeypatch):
    for key in (
        "DEMO_AUTH_USER",
        "DEMO_AUTH_PASS",
        "DIG_IN_REQUIRE_AUTH",
        "FLY_APP_NAME",
    ):
        monkeypatch.delenv(key, raising=False)
    app = FastAPI()
    app.add_middleware(DemoAccessMiddleware)

    @app.get("/api/v2/state")
    def state():
        return {"sensitive": "demo state"}

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    return TestClient(app)


def test_both_unset_is_local_dev(gated):
    assert gated.get("/api/v2/state").status_code == 200


@pytest.mark.parametrize(
    "values",
    [
        {"DEMO_AUTH_USER": "demo"},
        {"DEMO_AUTH_PASS": "test-only"},
        {"FLY_APP_NAME": "test-app"},
        {"DIG_IN_REQUIRE_AUTH": "1"},
    ],
)
def test_partial_or_deployed_auth_fails_closed(gated, monkeypatch, values):
    for k, v in values.items():
        monkeypatch.setenv(k, v)
    assert gated.get("/api/v2/state").status_code == 401
    assert gated.get("/healthz").status_code == 200


def test_valid_auth_and_preflight(gated, monkeypatch):
    monkeypatch.setenv("DEMO_AUTH_USER", "demo")
    monkeypatch.setenv("DEMO_AUTH_PASS", "test-only")
    assert gated.get("/api/v2/state", auth=("demo", "test-only")).status_code == 200
    assert gated.get("/api/v2/state", auth=("demo", "wrong")).status_code == 401
    assert (
        gated.get(
            "/api/v2/state", headers={"Authorization": "Basic invalid"}
        ).status_code
        == 401
    )
    assert (
        gated.get("/api/v2/state", headers={"Authorization": "Basic /w=="}).status_code
        == 401
    )
    assert gated.get("/openapi.json").status_code == 401
    assert gated.options("/api/v2/state").status_code != 401
