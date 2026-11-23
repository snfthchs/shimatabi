import datetime
from typing import Any

import pytest

from app.ai.mock_provider import GUIDE_TEXT, MockProvider
from app.ai.provider import Candidate, Conditions, Relaxation
from app.models import Category
from tests.scenario import NOW

provider = MockProvider()
TODAY = NOW.date()  # 2026年11月24日（火）


def extract(message: str) -> dict[str, Any]:
    """取り出された条件のうち、読み取れたもの（None でないもの）だけを返す。"""
    return provider.extract_conditions(message, NOW).model_dump(exclude_none=True)


def day(offset: int) -> datetime.date:
    return TODAY + datetime.timedelta(days=offset)


MORNING = {"time_from": datetime.time(6), "time_to": datetime.time(12)}
AFTERNOON = {"time_from": datetime.time(12), "time_to": datetime.time(18)}


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        # デモの文
        (
            "今日の午後、那覇から行ける子連れOKの体験ある？",
            {"date": TODAY, **AFTERNOON, "max_minutes_from_naha": 60, "kids_ok": True},
        ),
        (
            "明日の朝、シュノーケルをしたい",
            {"date": day(1), **MORNING, "category": Category.MARINE},
        ),
        (
            "あさって、3人で雨でも楽しめるものは？",
            {"date": day(2), "party_size": 3, "rain_ok": True},
        ),
        ("明後日に行きたい", {"date": day(2)}),
        ("午前中がいい", MORNING),
        ("夜に行きたい", {"time_from": datetime.time(18)}),
        # 日付
        (
            "11月30日の夜、恩納村で",
            {"date": datetime.date(2026, 11, 30), "time_from": datetime.time(18), "area": "恩納村"},
        ),
        ("11/30に参加したい", {"date": datetime.date(2026, 11, 30)}),
        ("今日行きたい", {"date": TODAY}),
        ("1月5日に行きたい", {"date": datetime.date(2027, 1, 5)}),  # 過ぎた日付は、来年
        ("2月30日に行きたい", {}),  # 存在しない日付は、読み取らない
        ("13月40日", {}),
        # 人数
        ("大人2人と子供1人で行きたい", {"party_size": 3, "kids_ok": True}),
        ("2人と3人", {"party_size": 5}),
        ("三人で星を見たい", {"party_size": 3, "category": Category.NATURE}),
        ("３人で", {"party_size": 3}),  # 全角
        ("ひとりで", {"party_size": 1}),
        ("ふたりで", {"party_size": 2}),
        ("0人で", {}),
        ("100人で", {}),
        # 子連れ・雨
        ("家族で屋内がいい", {"kids_ok": True, "rain_ok": True}),
        ("台風が心配", {"rain_ok": True}),
        # 場所
        ("やんばるで遊びたい", {"area": "国頭村"}),
        ("那覇市内で遊びたい", {"area": "那覇市"}),
        ("那覇空港から1時間以内", {"max_minutes_from_naha": 60}),
        ("那覇から30分以内で行きたい", {"max_minutes_from_naha": 30}),
        ("那覇から2時間以内", {"max_minutes_from_naha": 120}),
        # 種類
        ("そばが食べたい", {"category": Category.FOOD}),
        ("染め物をしたい", {"category": Category.CRAFT}),
        ("海と料理が好き", {}),  # 複数の種類が混ざったら、絞らない
        # 読み取れない文
        ("こんにちは", {}),
        ("来週どこか", {}),
    ],
)
def test_extract_conditions(message: str, expected: dict[str, Any]) -> None:
    assert extract(message) == expected


@pytest.mark.parametrize(
    "message",
    ["!!!", "あ" * 500, "😀", "1" * 500, "月日", "0/0", "99/99", "\u0000", "　", "00月00日"],
)
def test_extraction_never_raises_on_odd_input(message: str) -> None:
    provider.extract_conditions(message, NOW)  # 例外が出なければよい


def test_relative_dates_follow_the_japan_time_date() -> None:
    # UTCでは前日の23:30でも、日本時間では翌日の8:30。「今日」は、日本時間の日付。
    now_utc = datetime.datetime(2026, 11, 23, 23, 30, tzinfo=datetime.UTC)

    conditions = provider.extract_conditions("今日", now_utc)

    assert conditions.date == datetime.date(2026, 11, 24)


# ---- 返答文 ----


def test_reply_for_no_conditions_guides_to_the_list() -> None:
    reply = provider.compose_reply(Conditions(), [], [])

    assert reply == GUIDE_TEXT
    assert "一覧" in reply


def test_reply_with_candidates_summarizes_conditions_and_lists_them() -> None:
    conditions = Conditions(
        date=TODAY,
        time_from=datetime.time(12),
        time_to=datetime.time(18),
        kids_ok=True,
        max_minutes_from_naha=60,
    )
    candidates = [Candidate(1, "海の体験", "概要", "子連れOK・残り4席", 6500)]

    reply = provider.compose_reply(conditions, candidates, [])

    assert "11月24日の午後、子連れOK、那覇から60分以内" in reply
    assert "1件の体験が見つかりました" in reply
    assert "・海の体験（子連れOK・残り4席）" in reply
    assert "予約できます" in reply


def test_reply_with_no_candidates_proposes_relaxations() -> None:
    reply = provider.compose_reply(
        Conditions(rain_ok=True, date=TODAY),
        [],
        [Relaxation("雨の条件", 2), Relaxation("日付の条件", 1)],
    )

    assert "見つかりませんでした" in reply
    assert "・雨の条件を外すと、2件あります" in reply
    assert "・日付の条件を外すと、1件あります" in reply


def test_reply_with_no_candidates_and_no_relaxations() -> None:
    reply = provider.compose_reply(Conditions(party_size=3), [], [])

    assert "3人" in reply
    assert "条件を変えて" in reply
    assert "一覧" in reply


@pytest.mark.parametrize(
    ("conditions", "expected"),
    [
        (Conditions(party_size=2, category=Category.CRAFT), "2人、工芸の体験"),
        (Conditions(area="恩納村", rain_ok=True), "雨でも楽しめる、恩納村"),
        (Conditions(time_from=datetime.time(9), time_to=datetime.time(11)), "9:00〜11:00"),
        (Conditions(time_from=datetime.time(15)), "15:00以降"),
        (Conditions(time_to=datetime.time(10, 30)), "10:30まで"),
    ],
)
def test_conditions_are_described_in_japanese(conditions: Conditions, expected: str) -> None:
    reply = provider.compose_reply(conditions, [], [])

    assert expected in reply
