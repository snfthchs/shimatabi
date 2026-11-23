"""旅行者向け: 体験の一覧と詳細（`/api/experiences`）。認証は不要。"""

import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import NowDep, SessionDep
from app.models import Category, Experience, Slot
from app.schemas import ExperienceDetail, ExperienceListItem, SlotOut
from app.services.experience_search import (
    SearchCriteria,
    get_experience_with_open_slots,
    remaining_seats,
    search_experiences,
)

router = APIRouter(prefix="/api/experiences", tags=["experiences"])


def slot_out(slot: Slot) -> SlotOut:
    remaining = remaining_seats(slot)
    return SlotOut(
        id=slot.id,
        starts_at=slot.starts_at,
        capacity=slot.capacity,
        remaining=remaining,
        is_full=remaining <= 0,
    )


def _list_item_values(experience: Experience, slots: list[Slot]) -> dict[str, object]:
    return {
        "id": experience.id,
        "title": experience.title,
        "summary": experience.summary,
        "category": experience.category,
        "area": experience.area,
        "price_yen": experience.price_yen,
        "duration_minutes": experience.duration_minutes,
        "kids_ok": experience.kids_ok,
        "min_age": experience.min_age,
        "rain_ok": experience.rain_ok,
        "minutes_from_naha": experience.minutes_from_naha,
        "confirmation_mode": experience.confirmation_mode,
        "photo_url": experience.photo_url,
        "business_name": experience.business.name,
        "slots": [slot_out(slot) for slot in slots],
    }


def experience_list_item(experience: Experience, slots: list[Slot]) -> ExperienceListItem:
    return ExperienceListItem.model_validate(_list_item_values(experience, slots))


@router.get("", response_model=list[ExperienceListItem])
def list_experiences(
    session: SessionDep,
    now: NowDep,
    date: datetime.date | None = None,
    party_size: Annotated[int, Query(ge=1, le=50)] = 1,
    kids_ok: bool | None = None,
    rain_ok: bool | None = None,
    area: str | None = None,
    category: Category | None = None,
    max_minutes_from_naha: Annotated[int | None, Query(ge=0)] = None,
) -> list[ExperienceListItem]:
    """条件に合う、受付中の便を持つ体験を返す。`date` は、日本時間の日付。"""
    criteria = SearchCriteria(
        date=date,
        party_size=party_size,
        kids_ok=kids_ok,
        rain_ok=rain_ok,
        area=area,
        category=category.value if category is not None else None,
        max_minutes_from_naha=max_minutes_from_naha,
    )
    results = search_experiences(session, criteria, now)
    return [experience_list_item(result.experience, result.slots) for result in results]


@router.get("/{experience_id}", response_model=ExperienceDetail)
def get_experience(experience_id: int, session: SessionDep, now: NowDep) -> ExperienceDetail:
    """体験の詳細と、これから始まる受付中の便（満席のものも、残席0で含める）を返す。"""
    result = get_experience_with_open_slots(session, experience_id, now)
    experience = result.experience
    return ExperienceDetail.model_validate(
        {
            **_list_item_values(experience, result.slots),
            "description": experience.description,
            "meeting_point": experience.meeting_point,
            "map_url": experience.map_url,
        }
    )
