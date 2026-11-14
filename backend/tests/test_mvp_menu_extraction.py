"""OCR yields reviewable evidence, never operational menu changes."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mvp import api
from app.mvp import menu_extraction as extraction
from app.mvp.domain import Restaurant


@pytest.mark.parametrize(
    "mime,data",
    [
        ("image/png", b"bad"),
        ("text/plain", b"Soup"),
        ("application/pdf", b"%PDF-" + b"x" * extraction.MAX_UPLOAD),
    ],
)
def test_rejects_invalid_input(mime, data):
    with pytest.raises(ValueError):
        extraction.extract_menu(data, mime)


def test_grouping_and_unknown_kitchen_fields(monkeypatch):
    monkeypatch.setattr(
        extraction,
        "ocr_pages",
        lambda *_: [
            [
                "MENU",
                "Tomato Soup $9.00",
                "Roasted tomato and basil.",
                "BASIL PASTA",
                "Fresh basil.",
            ]
        ],
    )
    result = extraction.extract_menu(b"%PDF-demo", "application/pdf")
    assert [i["name"] for i in result["items"]] == ["Tomato Soup", "BASIL PASTA"]
    assert result["items"][0]["price_cents"] == 900
    assert result["items"][0]["description"] == "Roasted tomato and basil."
    assert all("recipe" not in i for i in result["items"])
    assert result["requires_human_review"] and result["warnings"]


def test_endpoint_auth_and_no_activation(monkeypatch):
    restaurant = Restaurant()
    monkeypatch.setattr(api, "restaurant", restaurant)
    monkeypatch.setattr(extraction, "ocr_pages", lambda *_: [["TOMATO SOUP"]])
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        before = restaurant.snapshot()
        headers = {"Content-Type": "application/pdf"}
        assert (
            client.post(
                "/api/v2/menu/extract", content=b"%PDF-test", headers=headers
            ).status_code
            == 409
        )
        headers["X-Demo-Session"] = restaurant.session("lead-1")["session_id"]
        response = client.post(
            "/api/v2/menu/extract", content=b"%PDF-test", headers=headers
        )
        assert (
            response.status_code == 200
            and response.json()["items"][0]["name"] == "TOMATO SOUP"
        )
        assert restaurant.snapshot() == before and not restaurant.outbox.pending()


def test_unavailable_and_empty_ocr(monkeypatch):
    monkeypatch.setattr(extraction, "extraction_status", lambda: {"available": False})
    with pytest.raises(extraction.ExtractionUnavailable):
        extraction.ocr_pages(b"x", "image/png")
    monkeypatch.setattr(extraction, "ocr_pages", lambda *_: [[]])
    with pytest.raises(ValueError):
        extraction.extract_menu(b"%PDF-test", "application/pdf")
