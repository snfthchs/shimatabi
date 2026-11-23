"""検索・APIのテストで使う、架空の体験と便のそろい。

時刻は、`NOW`（2026年11月24日 10:00、日本時間）に固定する。`clock` フィクスチャの
初期値（UTCの01:00）と同じ時刻である。
"""

import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.clock import JST
from app.models import Category, ConfirmationMode, Experience, Slot, SlotStatus
from tests.factories import create_business, create_experience, create_slot

NOW = datetime.datetime(2026, 11, 24, 10, 0, tzinfo=JST)


def at(day_offset: int, hour: int, minute: int = 0) -> datetime.datetime:
    """`NOW` の日から数えて、`day_offset` 日後の、日本時間の `hour:minute`。"""
    day = NOW.date() + datetime.timedelta(days=day_offset)
    return datetime.datetime.combine(day, datetime.time(hour, minute), tzinfo=JST)


@dataclass
class Catalog:
    marine: Experience  # 海・恩納村・子連れ可・雨天不可・那覇から60分
    craft: Experience  # 工芸・那覇市・子連れ不可・雨天可・那覇から10分
    far: Experience  # 自然・国頭村・子連れ可・雨天不可・那覇から120分
    marine_today_afternoon: Slot  # 今日13:00・定員8
    marine_past: Slot  # 今日9:00（過ぎている）
    marine_cancelled: Slot  # 今日15:00（中止）
    marine_tomorrow: Slot  # 明日9:00・定員4
    craft_today_full: Slot  # 今日14:00・定員2で満席
    craft_tomorrow: Slot  # 明日10:00・定員4
    far_tonight: Slot  # 今日20:00・定員6


def build_catalog(session: Session) -> Catalog:
    """体験3件と、さまざまな状態の便を作って、コミットする。"""
    marine = create_experience(
        session,
        create_business(session, "海の事業者"),
        title="海の体験",
        category=Category.MARINE,
        area="恩納村",
        kids_ok=True,
        rain_ok=False,
        minutes_from_naha=60,
        confirmation_mode=ConfirmationMode.INSTANT,
    )
    craft = create_experience(
        session,
        create_business(session, "工芸の事業者"),
        title="工芸の体験",
        category=Category.CRAFT,
        area="那覇市",
        kids_ok=False,
        rain_ok=True,
        minutes_from_naha=10,
        confirmation_mode=ConfirmationMode.APPROVAL,
    )
    far = create_experience(
        session,
        create_business(session, "自然の事業者"),
        title="夜の体験",
        category=Category.NATURE,
        area="国頭村",
        kids_ok=True,
        rain_ok=False,
        minutes_from_naha=120,
        confirmation_mode=ConfirmationMode.INSTANT,
    )
    catalog = Catalog(
        marine=marine,
        craft=craft,
        far=far,
        marine_today_afternoon=create_slot(session, marine, starts_at=at(0, 13), capacity=8),
        marine_past=create_slot(session, marine, starts_at=at(0, 9), capacity=8),
        marine_cancelled=create_slot(
            session, marine, starts_at=at(0, 15), capacity=8, status=SlotStatus.CANCELLED
        ),
        marine_tomorrow=create_slot(session, marine, starts_at=at(1, 9), capacity=4),
        craft_today_full=create_slot(
            session, craft, starts_at=at(0, 14), capacity=2, booked_count=2
        ),
        craft_tomorrow=create_slot(session, craft, starts_at=at(1, 10), capacity=4),
        far_tonight=create_slot(session, far, starts_at=at(0, 20), capacity=6),
    )
    session.commit()
    return catalog
