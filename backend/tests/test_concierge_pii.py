"""AIに渡す前の、個人情報のチェックのテスト（サービスとAPI）。

「AIの入力に、個人情報が入らない」ことを、2つの面から確かめる。

1. 旅行者の文章: 個人情報らしき文字列は、AIに渡す前に伏せる
2. DBの内容: 予約者の個人情報は、AIプロバイダーのどの引数にも出てこない
"""

import datetime
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.mock_provider import MockProvider
from app.ai.provider import Candidate, Conditions, Relaxation
from app.deps import get_concierge_provider
from app.main import app
from app.models import BookingStatus
from app.services.concierge import run_concierge
from tests.factories import create_booking
from tests.scenario import NOW, Catalog, build_catalog


class SpyProvider:
    """呼ばれたときの引数を、すべて記録するプロバイダー。中身は、モックと同じ。"""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.recorded: list[str] = []

    def extract_conditions(self, message: str, now: datetime.datetime) -> Conditions:
        self.messages.append(message)
        self.recorded.append(repr((message, now)))
        return MockProvider().extract_conditions(message, now)

    def compose_reply(
        self,
        conditions: Conditions,
        candidates: Sequence[Candidate],
        relaxations: Sequence[Relaxation],
    ) -> str:
        self.recorded.append(repr((conditions, list(candidates), list(relaxations))))
        return MockProvider().compose_reply(conditions, candidates, relaxations)


@pytest.fixture
def catalog(session: Session) -> Catalog:
    return build_catalog(session)


# ---- 旅行者の文章 ----


@pytest.mark.parametrize(
    ("message", "secret"),
    [
        ("今日の午後、子連れで。090-1234-5678まで", "090-1234-5678"),
        ("今日の午後、子連れで。０９０－１２３４－５６７８まで", "1234"),
        ("今日の午後、子連れで。taro@example.com まで", "taro@example.com"),
        ("今日の午後、子連れで。〒900-0001", "900-0001"),
        ("今日の午後、子連れで。4111 1111 1111 1111", "4111"),
    ],
)
def test_personal_info_is_masked_before_it_reaches_the_provider(
    session: Session, catalog: Catalog, message: str, secret: str
) -> None:
    spy = SpyProvider()

    result = run_concierge(session, spy, message, NOW)

    assert result.pii_masked is True
    assert len(spy.messages) == 1
    assert secret not in spy.messages[0]
    assert "[" in spy.messages[0]  # 印に置き換わっている
    assert secret not in "".join(spy.recorded)
    assert secret not in result.reply
    # 伏せたあとも、条件は読み取れて、提案は出る
    assert result.conditions.kids_ok is True
    assert len(result.suggestions) == 1


def test_a_request_without_personal_info_is_passed_through_unchanged(
    session: Session, catalog: Catalog
) -> None:
    spy = SpyProvider()
    message = "今日の午後、子連れで行ける体験ある？"

    result = run_concierge(session, spy, message, NOW)

    assert result.pii_masked is False
    assert spy.messages == [message]


# ---- DBの内容（予約者の個人情報） ----


def test_booking_guests_personal_info_never_reaches_the_provider(
    session: Session, catalog: Catalog
) -> None:
    create_booking(
        session,
        catalog.marine_today_afternoon,
        booking_number="SPYA234567",
        status=BookingStatus.CONFIRMED,
        guest_name="架空 太郎",
        guest_phone="090-7777-8888",
        guest_email="spy-guest@example.com",
    )
    session.commit()
    spy = SpyProvider()

    # 候補が出る相談と、0件になって条件の緩め方が出る相談の、両方を通す
    found = run_concierge(session, spy, "今日の午後、子連れで行ける体験ある？", NOW)
    not_found = run_concierge(session, spy, "今日の午後、雨でも子連れで工芸の体験", NOW)

    assert found.suggestions
    assert not not_found.suggestions
    recorded = "".join(spy.recorded)
    for secret in (
        "架空 太郎",
        "架空",
        "090-7777-8888",
        "7777",
        "spy-guest@example.com",
        "SPYA234567",
    ):
        assert secret not in recorded
    assert "架空" not in found.reply + not_found.reply


# ---- API ----


def test_the_api_reports_masking_and_never_echoes_the_personal_info(
    client: TestClient, catalog: Catalog
) -> None:
    spy = SpyProvider()
    app.dependency_overrides[get_concierge_provider] = lambda: spy

    response = client.post(
        "/api/concierge/search",
        json={"message": "今日の午後、子連れで。連絡先は090-1234-5678"},
    )

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["pii_masked"] is True
    assert "090-1234-5678" not in response.text
    assert "090-1234-5678" not in "".join(spy.recorded)
    assert response.headers["cache-control"] == "no-store"


def test_the_api_reports_no_masking_for_an_ordinary_request(
    client: TestClient, catalog: Catalog
) -> None:
    response = client.post(
        "/api/concierge/search", json={"message": "今日の午後、子連れで行ける体験ある？"}
    )

    assert response.status_code == 200
    assert response.json()["pii_masked"] is False
