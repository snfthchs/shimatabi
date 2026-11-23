import datetime
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import JST
from app.models import BookingStatus, BusinessUser, Slot, SlotStatus
from tests.factories import create_booking, create_business, create_experience, create_slot


def test_slot_defaults(session: Session) -> None:
    experience = create_experience(session, create_business(session))
    slot = Slot(
        experience_id=experience.id,
        starts_at=datetime.datetime(2030, 1, 15, 9, 0, tzinfo=JST),
        capacity=4,
    )
    session.add(slot)
    session.flush()

    assert slot.booked_count == 0
    assert slot.status == SlotStatus.OPEN


@pytest.mark.parametrize(
    "overrides",
    [
        {"capacity": 4, "booked_count": 5},  # 定員を超える
        {"capacity": 4, "booked_count": -1},  # マイナス
        {"capacity": 0, "booked_count": 0},  # 定員が0
        {"status": "unknown"},  # 決められていない状態
    ],
)
def test_slot_constraints_reject_invalid_values(
    session: Session, overrides: dict[str, Any]
) -> None:
    experience = create_experience(session, create_business(session))

    with pytest.raises(IntegrityError):
        create_slot(session, experience, **overrides)


def test_slot_may_be_filled_up_to_capacity(session: Session) -> None:
    experience = create_experience(session, create_business(session))

    slot = create_slot(session, experience, capacity=4, booked_count=4)

    assert slot.booked_count == slot.capacity


@pytest.mark.parametrize(
    "overrides",
    [
        {"category": "unknown"},
        {"confirmation_mode": "unknown"},
        {"price_yen": -1},
        {"duration_minutes": 0},
    ],
)
def test_experience_constraints_reject_invalid_values(
    session: Session, overrides: dict[str, Any]
) -> None:
    business = create_business(session)

    with pytest.raises(IntegrityError):
        create_experience(session, business, **overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"party_size": 0},
        {"status": "unknown"},
    ],
)
def test_booking_constraints_reject_invalid_values(
    session: Session, overrides: dict[str, Any]
) -> None:
    experience = create_experience(session, create_business(session))
    slot = create_slot(session, experience)

    with pytest.raises(IntegrityError):
        create_booking(session, slot, **overrides)


def test_booking_number_must_be_unique(session: Session) -> None:
    experience = create_experience(session, create_business(session))
    slot = create_slot(session, experience)
    create_booking(session, slot, booking_number="TESTA23456")

    with pytest.raises(IntegrityError):
        create_booking(session, slot, booking_number="TESTA23456")


def test_login_id_must_be_unique(session: Session) -> None:
    business = create_business(session)
    session.add(BusinessUser(business_id=business.id, login_id="demo", password_hash="x"))
    session.flush()

    session.add(BusinessUser(business_id=business.id, login_id="demo", password_hash="y"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_foreign_keys_are_enforced(session: Session) -> None:
    # SQLiteは、既定では外部キーを確認しない。接続のたびに有効にしていることの確認。
    with pytest.raises(IntegrityError):
        create_slot(
            session, create_experience(session, create_business(session)), experience_id=9999
        )


def test_booking_defaults(session: Session) -> None:
    experience = create_experience(session, create_business(session))
    slot = create_slot(session, experience)

    booking = create_booking(session, slot, status=BookingStatus.CONFIRMED)

    assert booking.created_at is not None
    assert booking.created_at.utcoffset() == datetime.timedelta(0)
    assert booking.decided_at is None
