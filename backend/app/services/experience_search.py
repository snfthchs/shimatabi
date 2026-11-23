"""体験の検索（絞り込みと、受付中の便）。

旅行者向けの体験の一覧APIと、AIコンシェルジュ（Issue E）で共有する。
AIは、検索条件を作るだけで、検索そのものは、ここで行う（登録済みの体験だけが提案される）。
"""

import datetime
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.clock import JST, jst_day_range
from app.errors import NotFoundError
from app.models import Experience, Slot, SlotStatus


@dataclass(frozen=True)
class SearchCriteria:
    """体験の検索条件。すべて省略できる。"""

    date: datetime.date | None = None  # 日本時間の日付
    time_from: datetime.time | None = None  # 日本時間の時刻（この時刻以降の便）
    time_to: datetime.time | None = None  # 日本時間の時刻（この時刻より前の便）
    party_size: int = 1  # 人数。残席が、この人数以上の便だけを対象にする
    kids_ok: bool | None = None  # True のときだけ、子連れ可の体験に絞る
    rain_ok: bool | None = None  # True のときだけ、雨でも実施できる体験に絞る
    area: str | None = None
    category: str | None = None
    max_minutes_from_naha: int | None = None


@dataclass(frozen=True)
class SearchResult:
    """検索結果の1件。体験と、条件に合う受付中の便（開始が早い順）。"""

    experience: Experience
    slots: list[Slot]


def remaining_seats(slot: Slot) -> int:
    """便の残席。"""
    return slot.capacity - slot.booked_count


def _in_time_window(
    slot: Slot, time_from: datetime.time | None, time_to: datetime.time | None
) -> bool:
    local_time = slot.starts_at.astimezone(JST).time()
    if time_from is not None and local_time < time_from:
        return False
    return not (time_to is not None and local_time >= time_to)


def search_experiences(
    session: Session,
    criteria: SearchCriteria,
    now: datetime.datetime,
    *,
    slots_per_experience: int | None = 5,
) -> list[SearchResult]:
    """条件に合う、受付中の便を持つ体験を返す。

    便が1つも合わない体験は、結果に含めない。結果は、いちばん早い便が早い順に並べる。
    `slots_per_experience` は、体験ごとに返す便の数の上限（`None` なら、すべて）。
    """
    statement = (
        select(Slot)
        .join(Experience, Slot.experience_id == Experience.id)
        .options(contains_eager(Slot.experience).joinedload(Experience.business))
        .where(
            Slot.status == SlotStatus.OPEN,
            Slot.starts_at > now,
            Slot.capacity - Slot.booked_count >= criteria.party_size,
        )
        .order_by(Slot.starts_at, Slot.id)
    )
    if criteria.kids_ok:
        statement = statement.where(Experience.kids_ok.is_(True))
    if criteria.rain_ok:
        statement = statement.where(Experience.rain_ok.is_(True))
    if criteria.area is not None:
        statement = statement.where(Experience.area == criteria.area)
    if criteria.category is not None:
        statement = statement.where(Experience.category == criteria.category)
    if criteria.max_minutes_from_naha is not None:
        statement = statement.where(Experience.minutes_from_naha <= criteria.max_minutes_from_naha)
    if criteria.date is not None:
        start, end = jst_day_range(criteria.date)
        statement = statement.where(Slot.starts_at >= start, Slot.starts_at < end)

    # 体験ごとに、便をまとめる（辞書は、最初に入れた順を保つ。= 早い便を持つ体験が先）
    grouped: dict[int, SearchResult] = {}
    for slot in session.scalars(statement):
        if not _in_time_window(slot, criteria.time_from, criteria.time_to):
            continue
        result = grouped.setdefault(slot.experience_id, SearchResult(slot.experience, []))
        if slots_per_experience is None or len(result.slots) < slots_per_experience:
            result.slots.append(slot)
    return list(grouped.values())


def get_experience_with_open_slots(
    session: Session, experience_id: int, now: datetime.datetime
) -> SearchResult:
    """体験1件と、これから始まる受付中の便を、すべて（満席のものも含めて）返す。"""
    experience = session.scalar(
        select(Experience)
        .options(joinedload(Experience.business))
        .where(Experience.id == experience_id)
    )
    if experience is None:
        raise NotFoundError("体験が見つかりません。")
    slots = list(
        session.scalars(
            select(Slot)
            .where(
                Slot.experience_id == experience_id,
                Slot.status == SlotStatus.OPEN,
                Slot.starts_at > now,
            )
            .order_by(Slot.starts_at, Slot.id)
        )
    )
    return SearchResult(experience, slots)
