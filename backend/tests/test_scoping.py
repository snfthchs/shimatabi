import pytest
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import Business
from app.scoping import (
    business_bookings,
    business_experiences,
    business_slots,
    get_booking_or_404,
    get_slot_or_404,
)
from tests.factories import create_booking, create_business, create_experience, create_slot


class TwoBusinesses:
    """事業者A・Bと、それぞれの体験・便・予約。"""

    def __init__(self, session: Session) -> None:
        self.a = create_business(session, "事業者A")
        self.b = create_business(session, "事業者B")
        self.experience_a = create_experience(session, self.a, title="A体験")
        self.experience_b = create_experience(session, self.b, title="B体験")
        self.slot_a = create_slot(session, self.experience_a)
        self.slot_b = create_slot(session, self.experience_b)
        self.booking_a = create_booking(session, self.slot_a, booking_number="TESTA23456")
        self.booking_b = create_booking(session, self.slot_b, booking_number="TESTB23456")


@pytest.fixture
def data(session: Session) -> TwoBusinesses:
    return TwoBusinesses(session)


def test_queries_return_only_the_businesses_own_data(session: Session, data: TwoBusinesses) -> None:
    experience_ids = [e.id for e in session.scalars(business_experiences(data.a.id))]
    slot_ids = [s.id for s in session.scalars(business_slots(data.a.id))]
    booking_ids = [b.id for b in session.scalars(business_bookings(data.a.id))]

    assert experience_ids == [data.experience_a.id]
    assert slot_ids == [data.slot_a.id]
    assert booking_ids == [data.booking_a.id]


def test_a_business_with_no_data_gets_nothing(session: Session) -> None:
    empty: Business = create_business(session, "データのない事業者")

    assert list(session.scalars(business_bookings(empty.id))) == []


def test_get_booking_or_404_returns_the_own_booking(session: Session, data: TwoBusinesses) -> None:
    booking = get_booking_or_404(session, data.a.id, data.booking_a.id)

    assert booking.id == data.booking_a.id


def test_another_businesses_booking_is_404_just_like_a_missing_one(
    session: Session, data: TwoBusinesses
) -> None:
    with pytest.raises(NotFoundError) as other_business:
        get_booking_or_404(session, data.a.id, data.booking_b.id)
    with pytest.raises(NotFoundError) as missing:
        get_booking_or_404(session, data.a.id, 99999)

    # 見えない理由（他社のもの／存在しない）を、区別できない
    assert other_business.value.status_code == missing.value.status_code == 404
    assert other_business.value.message == missing.value.message


def test_get_slot_or_404(session: Session, data: TwoBusinesses) -> None:
    assert get_slot_or_404(session, data.a.id, data.slot_a.id).id == data.slot_a.id

    with pytest.raises(NotFoundError):
        get_slot_or_404(session, data.a.id, data.slot_b.id)
