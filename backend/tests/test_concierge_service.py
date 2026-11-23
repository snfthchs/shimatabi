import datetime
import logging
from collections.abc import Sequence

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.mock_provider import GUIDE_TEXT, MockProvider
from app.ai.provider import Candidate, Conditions, Relaxation
from app.models import Experience
from app.services import concierge as concierge_service
from app.services.concierge import (
    FALLBACK_REPLY_FOUND,
    FALLBACK_REPLY_NOT_FOUND,
    MAX_SUGGESTIONS,
    SLOTS_PER_SUGGESTION,
    run_concierge,
)
from tests.factories import create_business, create_experience, create_slot
from tests.scenario import NOW, Catalog, at, build_catalog


class StubProvider:
    """テスト用のAIプロバイダー。条件を固定したり、わざと失敗させたりできる。"""

    def __init__(
        self,
        conditions: Conditions | None = None,
        *,
        fail_extract: bool = False,
        fail_compose: bool = False,
    ) -> None:
        self.conditions = conditions
        self.fail_extract = fail_extract
        self.fail_compose = fail_compose

    def extract_conditions(self, message: str, now: datetime.datetime) -> Conditions:
        if self.fail_extract:
            raise RuntimeError(f"SECRET: {message}")
        if self.conditions is not None:
            return self.conditions
        return MockProvider().extract_conditions(message, now)

    def compose_reply(
        self,
        conditions: Conditions,
        candidates: Sequence[Candidate],
        relaxations: Sequence[Relaxation],
    ) -> str:
        if self.fail_compose:
            raise RuntimeError("SECRET: compose failed")
        return MockProvider().compose_reply(conditions, candidates, relaxations)


@pytest.fixture
def catalog(session: Session) -> Catalog:
    return build_catalog(session)


def _run(session: Session, message: str, provider: StubProvider | None = None):  # type: ignore[no-untyped-def]
    return run_concierge(session, provider or StubProvider(), message, NOW)


def test_suggests_experiences_that_match_with_facts_as_the_reason(
    session: Session, catalog: Catalog
) -> None:
    result = _run(session, "今日の午後、子連れで行ける体験")

    assert [s.experience.id for s in result.suggestions] == [catalog.marine.id]
    suggestion = result.suggestions[0]
    assert [slot.id for slot in suggestion.slots] == [catalog.marine_today_afternoon.id]
    # 理由は、DBの事実から、アプリが作る
    assert suggestion.reason == (
        "子連れOK・那覇から約60分・11/24 13:00の便は残り8席・予約はすぐ確定"
    )
    assert "海の体験" in result.reply
    assert "1件の体験が見つかりました" in result.reply


def test_approval_experiences_say_that_confirmation_needs_approval(
    session: Session, catalog: Catalog
) -> None:
    result = _run(session, "明日、雨でも楽しめる")

    assert [s.experience.id for s in result.suggestions] == [catalog.craft.id]
    assert result.suggestions[0].reason.endswith("予約は事業者の承認後に確定")
    assert "雨でも実施" in result.suggestions[0].reason


def test_party_size_is_respected(session: Session, catalog: Catalog) -> None:
    result = _run(session, "今日6人で行きたい")

    # 残席が6以上の便だけ。工芸の今日の便は満席
    assert [s.experience.id for s in result.suggestions] == [catalog.marine.id, catalog.far.id]


def test_no_results_proposes_only_relaxations_that_find_something(
    session: Session, catalog: Catalog
) -> None:
    # 今日の午後で、雨でも実施できる体験は、ない（工芸は今日の便が満席）
    result = _run(session, "今日の午後、雨でも楽しめる体験")

    assert result.suggestions == []
    assert "見つかりませんでした" in result.reply
    # 雨の条件を外すと、海の体験が1件見つかる。時間帯や日付を外しても、見つからないので、提案しない
    assert "・雨の条件を外すと、1件あります" in result.reply
    assert "時間帯の条件" not in result.reply
    assert "日付の条件" not in result.reply


def test_relaxing_an_unknown_area_finds_everything(session: Session, catalog: Catalog) -> None:
    result = _run(session, "どこかで", StubProvider(Conditions(area="存在しない村")))

    assert result.suggestions == []
    # エリアの条件を外すと、受付中の便を持つ3つの体験すべてが見つかる
    assert "・エリアの条件を外すと、3件あります" in result.reply


def test_no_results_and_nothing_to_relax_when_there_are_no_slots_at_all(
    session: Session,
) -> None:
    # 便が1つもないDB。どの条件を外しても、見つからない
    result = _run(session, "子連れで", StubProvider(Conditions(kids_ok=True, party_size=2)))

    assert result.suggestions == []
    assert "条件を変えて" in result.reply
    assert "を外すと" not in result.reply


def test_no_conditions_guides_to_the_list_without_searching(
    session: Session, catalog: Catalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("条件がないときは、検索しない")

    monkeypatch.setattr(concierge_service, "search_experiences", fail)

    result = _run(session, "こんにちは")

    assert result.conditions.is_empty()
    assert result.suggestions == []
    assert result.reply == GUIDE_TEXT


def test_suggestions_come_only_from_the_database(session: Session, catalog: Catalog) -> None:
    known_ids = set(session.scalars(select(Experience.id)))

    # AIが、どんな条件を出しても、提案は、DBにある体験だけ
    for conditions in (
        Conditions(),
        Conditions(kids_ok=True),
        Conditions(area="存在しない村"),
        Conditions(max_minutes_from_naha=0),
    ):
        result = _run(session, "何でも", StubProvider(conditions))
        assert {s.experience.id for s in result.suggestions} <= known_ids


def test_suggestions_are_capped(session: Session, catalog: Catalog) -> None:
    business = create_business(session, "たくさんの事業者")
    for index in range(MAX_SUGGESTIONS + 3):
        experience = create_experience(session, business, title=f"追加の体験{index}")
        for hour in range(SLOTS_PER_SUGGESTION + 2):
            create_slot(session, experience, starts_at=at(1, 9 + hour), capacity=4)
    session.commit()

    result = _run(session, "明日、子連れで行ける体験")

    assert len(result.suggestions) == MAX_SUGGESTIONS
    assert all(len(s.slots) <= SLOTS_PER_SUGGESTION for s in result.suggestions)


def test_failing_extraction_falls_back_to_guidance_and_logs_only_the_exception_type(
    session: Session, catalog: Catalog, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    result = _run(session, "合言葉は青い鳥", StubProvider(fail_extract=True))

    assert result.suggestions == []
    assert result.reply == GUIDE_TEXT
    assert "RuntimeError" in caplog.text  # 例外の種類は、ログに残る
    assert "青い鳥" not in caplog.text  # 旅行者の文章は、ログに出ない
    assert "SECRET" not in caplog.text


def test_failing_reply_generation_still_returns_the_suggestions(
    session: Session, catalog: Catalog, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    found = _run(session, "今日の午後、子連れ", StubProvider(fail_compose=True))
    not_found = _run(session, "今日の午後、雨でも", StubProvider(fail_compose=True))

    assert len(found.suggestions) == 1
    assert found.reply == FALLBACK_REPLY_FOUND
    assert not_found.suggestions == []
    assert not_found.reply == FALLBACK_REPLY_NOT_FOUND
    assert "SECRET" not in caplog.text
