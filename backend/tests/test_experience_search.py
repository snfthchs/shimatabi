import datetime

import pytest
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.services.experience_search import (
    SearchCriteria,
    SearchResult,
    get_experience_with_open_slots,
    remaining_seats,
    search_experiences,
)
from tests.scenario import NOW, Catalog, at, build_catalog


@pytest.fixture
def catalog(session: Session) -> Catalog:
    return build_catalog(session)


def _titles(results: list[SearchResult]) -> list[str]:
    return [result.experience.title for result in results]


def test_without_criteria_only_open_future_slots_with_seats_are_returned(
    session: Session, catalog: Catalog
) -> None:
    results = search_experiences(session, SearchCriteria(), NOW)

    # 過ぎた便、中止の便、満席の便は含まれない。いちばん早い便が早い体験から並ぶ。
    assert _titles(results) == ["海の体験", "夜の体験", "工芸の体験"]
    marine = results[0]
    assert [slot.id for slot in marine.slots] == [
        catalog.marine_today_afternoon.id,
        catalog.marine_tomorrow.id,
    ]
    craft = results[2]
    assert [slot.id for slot in craft.slots] == [catalog.craft_tomorrow.id]


def test_filter_by_date_uses_the_japan_time_date(session: Session, catalog: Catalog) -> None:
    today = search_experiences(session, SearchCriteria(date=NOW.date()), NOW)
    tomorrow = search_experiences(
        session, SearchCriteria(date=NOW.date() + datetime.timedelta(days=1)), NOW
    )

    assert _titles(today) == ["海の体験", "夜の体験"]
    assert _titles(tomorrow) == ["海の体験", "工芸の体験"]


def test_filter_by_time_window(session: Session, catalog: Catalog) -> None:
    afternoon = SearchCriteria(time_from=datetime.time(12), time_to=datetime.time(18))

    results = search_experiences(session, afternoon, NOW)

    # 今日の13:00の便だけ。14:00の工芸は満席。明日の便と、20:00の便は、時間帯の外
    assert _titles(results) == ["海の体験"]
    assert [slot.id for slot in results[0].slots] == [catalog.marine_today_afternoon.id]


def test_time_window_end_is_exclusive(session: Session, catalog: Catalog) -> None:
    results = search_experiences(
        session, SearchCriteria(date=NOW.date(), time_to=datetime.time(13)), NOW
    )

    assert results == []  # 13:00の便は、13:00より前ではない


@pytest.mark.parametrize(
    ("criteria", "expected"),
    [
        (SearchCriteria(kids_ok=True), ["海の体験", "夜の体験"]),
        (SearchCriteria(rain_ok=True), ["工芸の体験"]),
        (SearchCriteria(area="那覇市"), ["工芸の体験"]),
        (SearchCriteria(category="nature"), ["夜の体験"]),
        (SearchCriteria(max_minutes_from_naha=60), ["海の体験", "工芸の体験"]),
        (SearchCriteria(kids_ok=True, max_minutes_from_naha=60), ["海の体験"]),
        # False や None は、絞り込まない（True のときだけ絞る）
        (SearchCriteria(kids_ok=False), ["海の体験", "夜の体験", "工芸の体験"]),
    ],
)
def test_filter_by_attributes(
    session: Session, catalog: Catalog, criteria: SearchCriteria, expected: list[str]
) -> None:
    assert _titles(search_experiences(session, criteria, NOW)) == expected


def test_party_size_excludes_slots_without_enough_seats(session: Session, catalog: Catalog) -> None:
    # 5人: 海の明日（定員4）、工芸の明日（定員4）は入らない。今日13:00（定員8）と夜（定員6）は入る
    results = search_experiences(session, SearchCriteria(party_size=5), NOW)

    assert _titles(results) == ["海の体験", "夜の体験"]
    assert [slot.id for slot in results[0].slots] == [catalog.marine_today_afternoon.id]


def test_slots_per_experience_limit(session: Session, catalog: Catalog) -> None:
    results = search_experiences(session, SearchCriteria(), NOW, slots_per_experience=1)

    assert all(len(result.slots) == 1 for result in results)


def test_experience_detail_includes_full_slots_but_not_past_or_cancelled(
    session: Session, catalog: Catalog
) -> None:
    result = get_experience_with_open_slots(session, catalog.craft.id, NOW)

    assert [slot.id for slot in result.slots] == [
        catalog.craft_today_full.id,
        catalog.craft_tomorrow.id,
    ]
    assert remaining_seats(result.slots[0]) == 0  # 満席も、残席0で含める

    marine = get_experience_with_open_slots(session, catalog.marine.id, NOW)
    assert catalog.marine_past.id not in [slot.id for slot in marine.slots]
    assert catalog.marine_cancelled.id not in [slot.id for slot in marine.slots]


def test_experience_detail_of_missing_experience_is_404(session: Session) -> None:
    with pytest.raises(NotFoundError):
        get_experience_with_open_slots(session, 99999, NOW)


def test_slot_times_are_evaluated_in_japan_time(session: Session, catalog: Catalog) -> None:
    # 今日20:00（日本時間）は、UTCでは今日11:00。UTCの「午前」ではなく、日本時間の20:00として扱う。
    evening = SearchCriteria(time_from=datetime.time(19), time_to=datetime.time(21))

    results = search_experiences(session, evening, NOW)

    assert [slot.id for slot in results[0].slots] == [catalog.far_tonight.id]
    assert at(0, 20).utcoffset() == datetime.timedelta(hours=9)
