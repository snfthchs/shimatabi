import datetime
import re

import pytest
from argon2 import PasswordHasher
from sqlalchemy import Engine, func, inspect, select
from sqlalchemy.orm import Session

from app.clock import JST
from app.config import Settings
from app.models import (
    ACTIVE_BOOKING_STATUSES,
    Booking,
    BookingStatus,
    Business,
    BusinessUser,
    Experience,
    Slot,
)
from app.seed import DAYS, DEMO_PASSWORD, SeedError, run_seed

# 火曜日の午前10時（日本時間）に、シードを実行したものとする。
NOW = datetime.datetime(2026, 11, 24, 10, 0, tzinfo=JST)

DEVELOPMENT = Settings(app_env="development", ai_provider="mock", pii_encryption_key=None)
PRODUCTION = Settings(app_env="production", ai_provider="mock", pii_encryption_key=None)

# 予約番号に使う文字（紛らわしい0・1・I・Oを除いた32種）で、10文字
BOOKING_NUMBER_PATTERN = re.compile(r"^[2-9A-HJ-NP-Z]{10}$")


@pytest.fixture
def seeded(engine: Engine) -> Engine:
    run_seed(engine, settings=DEVELOPMENT, reset=False, now=NOW)
    return engine


def _count(session: Session, model: type[Business] | type[Experience] | type[BusinessUser]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_creates_fictional_businesses_and_experiences(
    seeded: Engine, session: Session
) -> None:
    assert _count(session, Business) == 4
    assert _count(session, BusinessUser) == 4
    assert _count(session, Experience) == 8


def test_every_experience_has_slots_for_the_coming_week(seeded: Engine, session: Session) -> None:
    for experience in session.scalars(select(Experience)):
        assert experience.slots, experience.title

    dates = {slot.starts_at.astimezone(JST).date() for slot in session.scalars(select(Slot))}
    assert dates == {NOW.date() + datetime.timedelta(days=offset) for offset in range(DAYS)}


def test_slots_in_the_past_are_not_created(seeded: Engine, session: Session) -> None:
    for slot in session.scalars(select(Slot)):
        assert slot.starts_at > NOW


def test_there_are_open_slots_this_afternoon(seeded: Engine, session: Session) -> None:
    afternoon_start = datetime.datetime(2026, 11, 24, 12, 0, tzinfo=JST)
    afternoon_end = datetime.datetime(2026, 11, 24, 18, 0, tzinfo=JST)

    afternoon_slots = [
        slot
        for slot in session.scalars(select(Slot))
        if afternoon_start <= slot.starts_at < afternoon_end
    ]

    assert len(afternoon_slots) >= 3
    assert all(slot.booked_count < slot.capacity for slot in afternoon_slots)


def test_one_slot_is_full(seeded: Engine, session: Session) -> None:
    full_slots = [
        slot for slot in session.scalars(select(Slot)) if slot.booked_count == slot.capacity
    ]

    assert len(full_slots) == 1


def test_there_are_pending_bookings_to_approve(seeded: Engine, session: Session) -> None:
    pending = session.scalars(select(Booking).where(Booking.status == BookingStatus.PENDING)).all()

    assert len(pending) == 3


def test_booked_count_matches_active_bookings(seeded: Engine, session: Session) -> None:
    # 承認待ちと確定の予約の人数の合計が、便の予約済み人数と一致する（却下は数えない）
    for slot in session.scalars(select(Slot)):
        expected = sum(
            booking.party_size
            for booking in slot.bookings
            if booking.status in ACTIVE_BOOKING_STATUSES
        )
        assert slot.booked_count == expected


def test_booking_numbers_follow_the_format(seeded: Engine, session: Session) -> None:
    for booking in session.scalars(select(Booking)):
        assert BOOKING_NUMBER_PATTERN.match(booking.booking_number)


def test_guests_are_fictional(seeded: Engine, session: Session) -> None:
    for booking in session.scalars(select(Booking)):
        assert booking.guest_email.endswith("@example.com")
        assert booking.guest_phone.startswith("090-0000-")


def test_business_accounts_have_argon2id_hashes(seeded: Engine, session: Session) -> None:
    hasher = PasswordHasher()

    for user in session.scalars(select(BusinessUser)):
        assert user.password_hash.startswith("$argon2id$")
        assert DEMO_PASSWORD not in user.password_hash
        assert hasher.verify(user.password_hash, DEMO_PASSWORD)


def test_seed_is_refused_in_production(engine: Engine) -> None:
    with pytest.raises(SeedError, match="production"):
        run_seed(engine, settings=PRODUCTION, reset=True, now=NOW)

    # DBには、何も作られていない（テーブルを消して作り直すこともしていない）
    assert _count_rows(engine) == 0


def _count_rows(engine: Engine) -> int:
    with Session(engine) as session:
        return _count(session, Business)


def test_seed_refuses_to_run_twice_without_reset(seeded: Engine) -> None:
    with pytest.raises(SeedError, match="すでにデータがあります"):
        run_seed(seeded, settings=DEVELOPMENT, reset=False, now=NOW)


def test_reset_recreates_the_data_without_duplicates(seeded: Engine, session: Session) -> None:
    run_seed(seeded, settings=DEVELOPMENT, reset=True, now=NOW)

    with Session(seeded) as fresh_session:
        assert _count(fresh_session, Business) == 4
        assert _count(fresh_session, Experience) == 8


def test_seed_creates_all_tables_in_an_empty_db(tmp_path_factory: pytest.TempPathFactory) -> None:
    from app.db import create_db_engine

    engine = create_db_engine(f"sqlite:///{tmp_path_factory.mktemp('empty') / 'empty.db'}")

    run_seed(engine, settings=DEVELOPMENT, reset=False, now=NOW)

    assert set(inspect(engine).get_table_names()) == {
        "businesses",
        "business_users",
        "login_sessions",
        "experiences",
        "slots",
        "bookings",
    }
    engine.dispose()
