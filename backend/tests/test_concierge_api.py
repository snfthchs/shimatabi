import logging
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.provider import Candidate, Conditions, Relaxation
from app.deps import get_concierge_provider
from app.main import app
from tests.scenario import Catalog, build_catalog


@pytest.fixture
def catalog(session: Session) -> Catalog:
    return build_catalog(session)


def _ask(client: TestClient, message: str) -> Any:
    return client.post("/api/concierge/search", json={"message": message})


def test_search_returns_conditions_suggestions_and_reply(
    client: TestClient, catalog: Catalog
) -> None:
    response = _ask(client, "今日の午後、子連れで行ける体験ある？")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["conditions"]["date"] == "2026-11-24"
    assert body["conditions"]["time_from"] == "12:00:00"
    assert body["conditions"]["kids_ok"] is True
    assert body["conditions"]["category"] is None
    assert len(body["suggestions"]) == 1
    suggestion = body["suggestions"][0]
    assert suggestion["experience_id"] == catalog.marine.id
    assert suggestion["title"] == "海の体験"
    assert suggestion["confirmation_mode"] == "instant"
    assert suggestion["reason"].startswith("子連れOK")
    slot = suggestion["slots"][0]
    assert slot["id"] == catalog.marine_today_afternoon.id
    assert slot["remaining"] == 8
    assert slot["starts_at"] == "2026-11-24T04:00:00Z"
    assert "海の体験" in body["reply"]


def test_login_is_not_required(client: TestClient, catalog: Catalog) -> None:
    assert _ask(client, "明日、子連れ").status_code == 200


def test_no_results_returns_a_relaxation_proposal(client: TestClient, catalog: Catalog) -> None:
    body = _ask(client, "今日の午後、雨でも楽しめる体験").json()

    assert body["suggestions"] == []
    assert "雨の条件を外すと、1件あります" in body["reply"]


def test_unreadable_message_guides_to_the_list(client: TestClient, catalog: Catalog) -> None:
    body = _ask(client, "こんにちは").json()

    assert body["suggestions"] == []
    assert all(value is None for value in body["conditions"].values())
    assert "一覧" in body["reply"]


@pytest.mark.parametrize("message", ["", "   ", "あ" * 501])
def test_invalid_message_is_a_validation_error(client: TestClient, message: str) -> None:
    response = _ask(client, message)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_message_is_required(client: TestClient) -> None:
    assert client.post("/api/concierge/search", json={}).status_code == 422


def test_the_message_itself_is_not_in_the_response(client: TestClient, catalog: Catalog) -> None:
    secret = "固有の合言葉XYZ"

    response = _ask(client, f"{secret} 今日の午後、子連れ")

    assert response.status_code == 200
    assert secret not in response.text


def test_the_message_is_not_logged(
    client: TestClient, catalog: Catalog, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    secret = "固有の合言葉XYZ"

    _ask(client, f"{secret} 今日の午後、子連れ")

    assert secret not in caplog.text


class FailingProvider:
    def extract_conditions(self, message: str, now: Any) -> Conditions:
        raise RuntimeError(f"SECRET: {message}")

    def compose_reply(
        self,
        conditions: Conditions,
        candidates: Sequence[Candidate],
        relaxations: Sequence[Relaxation],
    ) -> str:
        raise RuntimeError("SECRET")


def test_a_failing_provider_does_not_break_the_api(
    client: TestClient, catalog: Catalog, caplog: pytest.LogCaptureFixture
) -> None:
    app.dependency_overrides[get_concierge_provider] = lambda: FailingProvider()
    caplog.set_level(logging.DEBUG)

    response = _ask(client, "秘密の合言葉ABC 今日の午後")

    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"] == []
    assert body["reply"]
    assert "秘密の合言葉ABC" not in caplog.text
    assert "SECRET" not in caplog.text
    assert "秘密の合言葉ABC" not in response.text
