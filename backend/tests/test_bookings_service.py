import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import InvalidStateError, NotFoundError, SlotUnavailableError
from app.models import Booking, BookingStatus, ConfirmationMode, Slot, SlotStatus
from app.services import bookings as bookings_service
from app.services.bookings import (
    NewBooking,
    approve_booking,
    find_booking_for_guest,
    reject_booking,
)
from app.services.bookings import create_booking as book_slot
from tests.factories import (
    create_booking,
    create_business,
    create_experience,
    create_slot,
)
from tests.scenario import NOW, at

PHONE = "09012345678"
EMAIL = "hanako@example.com"


def _new(slot: Slot, party_size: int = 2) -> NewBooking:
    return NewBooking(
        slot_id=slot.id,
        party_size=party_size,
        guest_name="山田 花子",
        guest_phone=PHONE,
        guest_email=EMAIL,
    )


def _booked_count(session: Session, slot_id: int) -> int:
    session.expire_all()
    slot = session.get(Slot, slot_id)
    assert slot is not None
    return slot.booked_count


def _booking_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Booking)) or 0


@pytest.fixture
def instant_slot(session: Session) -> Slot:
    experience = create_experience(
        session, create_business(session), confirmation_mode=ConfirmationMode.INSTANT
    )
    slot = create_slot(session, experience, starts_at=at(1, 9), capacity=4)
    session.commit()
    return slot


@pytest.fixture
def approval_slot(session: Session) -> Slot:
    experience = create_experience(
        session,
        create_business(session, "承認制の事業者"),
        confirmation_mode=ConfirmationMode.APPROVAL,
    )
    slot = create_slot(session, experience, starts_at=at(1, 10), capacity=4)
    session.commit()
    return slot


# ---- 予約の作成 ----


def test_instant_booking_is_confirmed_and_takes_seats(session: Session, instant_slot: Slot) -> None:
    booking = book_slot(session, _new(instant_slot, 3), NOW)

    assert booking.status == BookingStatus.CONFIRMED
    assert booking.party_size == 3
    assert len(booking.booking_number) == 10
    assert _booked_count(session, instant_slot.id) == 3


def test_approval_booking_is_pending_and_also_takes_seats(
    session: Session, approval_slot: Slot
) -> None:
    booking = book_slot(session, _new(approval_slot, 2), NOW)

    assert booking.status == BookingStatus.PENDING
    assert _booked_count(session, approval_slot.id) == 2  # 承認待ちも、定員に数える


def test_personal_info_is_saved_and_can_be_read_back(session: Session, instant_slot: Slot) -> None:
    booking = book_slot(session, _new(instant_slot), NOW)

    session.expire_all()
    saved = session.get(Booking, booking.id)

    assert saved is not None
    assert (saved.guest_name, saved.guest_phone, saved.guest_email) == ("山田 花子", PHONE, EMAIL)


def test_a_slot_can_be_filled_exactly_and_then_refuses_more(
    session: Session, instant_slot: Slot
) -> None:
    book_slot(session, _new(instant_slot, 3), NOW)
    book_slot(session, _new(instant_slot, 1), NOW)  # ちょうど定員（4）になる

    with pytest.raises(SlotUnavailableError):
        book_slot(session, _new(instant_slot, 1), NOW)

    assert _booked_count(session, instant_slot.id) == 4
    assert _booking_count(session) == 2


def test_party_larger_than_remaining_seats_is_refused_and_changes_nothing(
    session: Session, instant_slot: Slot
) -> None:
    book_slot(session, _new(instant_slot, 3), NOW)  # 残り1席

    with pytest.raises(SlotUnavailableError):
        book_slot(session, _new(instant_slot, 2), NOW)

    assert _booked_count(session, instant_slot.id) == 3  # 定員は、増えていない
    assert _booking_count(session) == 1  # 予約は、作られていない


def test_slot_that_has_started_is_refused(session: Session, instant_slot: Slot) -> None:
    after_start = instant_slot.starts_at + datetime.timedelta(minutes=1)

    with pytest.raises(SlotUnavailableError):
        book_slot(session, _new(instant_slot), after_start)

    assert _booking_count(session) == 0


def test_cancelled_slot_is_refused(session: Session, instant_slot: Slot) -> None:
    instant_slot.status = SlotStatus.CANCELLED
    session.commit()

    with pytest.raises(SlotUnavailableError):
        book_slot(session, _new(instant_slot), NOW)


def test_missing_slot_is_404(session: Session) -> None:
    with pytest.raises(NotFoundError):
        book_slot(
            session,
            NewBooking(
                slot_id=99999, party_size=1, guest_name="x", guest_phone=PHONE, guest_email=EMAIL
            ),
            NOW,
        )


def test_booking_number_collision_is_retried_without_double_counting(
    session: Session, instant_slot: Slot, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = book_slot(session, _new(instant_slot, 1), NOW)
    numbers = iter([existing.booking_number, existing.booking_number, "NEWNUMB234"])
    monkeypatch.setattr(bookings_service, "generate_booking_number", lambda: next(numbers))

    booking = book_slot(session, _new(instant_slot, 1), NOW)

    assert booking.booking_number == "NEWNUMB234"
    # 2回やり直したが、定員は、予約1件分（1人）だけ増えている（合計2人）
    assert _booked_count(session, instant_slot.id) == 2
    assert _booking_count(session) == 2


def test_booking_number_collision_gives_up_after_the_limit(
    session: Session, instant_slot: Slot, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = book_slot(session, _new(instant_slot, 1), NOW)
    monkeypatch.setattr(
        bookings_service, "generate_booking_number", lambda: existing.booking_number
    )

    with pytest.raises(RuntimeError):
        book_slot(session, _new(instant_slot, 1), NOW)

    assert _booked_count(session, instant_slot.id) == 1  # 失敗したので、定員は増えていない
    assert _booking_count(session) == 1


def test_generated_booking_numbers_use_the_safe_alphabet() -> None:
    for _ in range(200):
        number = bookings_service.generate_booking_number()
        assert len(number) == 10
        assert set(number) <= set(bookings_service.BOOKING_NUMBER_ALPHABET)
        assert not set(number) & set("01IO")  # 紛らわしい文字は使わない


# ---- 承認・却下 ----


def _pending(session: Session, slot: Slot, party_size: int = 2) -> Booking:
    booking = create_booking(
        session,
        slot,
        booking_number=f"PEND{party_size}23456"[:10],
        party_size=party_size,
        status=BookingStatus.PENDING,
    )
    slot.booked_count += party_size
    session.commit()
    return booking


def _business_id_of(slot: Slot) -> int:
    return slot.experience.business_id


def test_approve_confirms_the_booking_and_keeps_the_seats(
    session: Session, approval_slot: Slot
) -> None:
    booking = _pending(session, approval_slot, 2)

    approved = approve_booking(session, _business_id_of(approval_slot), booking.id, NOW)

    assert approved.status == BookingStatus.CONFIRMED
    assert approved.decided_at == NOW
    assert _booked_count(session, approval_slot.id) == 2  # 定員は、変わらない


def test_reject_marks_the_booking_and_releases_the_seats(
    session: Session, approval_slot: Slot
) -> None:
    booking = _pending(session, approval_slot, 3)

    rejected = reject_booking(session, _business_id_of(approval_slot), booking.id, NOW)

    assert rejected.status == BookingStatus.REJECTED
    assert rejected.decided_at == NOW
    assert _booked_count(session, approval_slot.id) == 0  # 押さえていた定員が、解放される


def test_a_processed_booking_cannot_be_processed_again(
    session: Session, approval_slot: Slot
) -> None:
    business_id = _business_id_of(approval_slot)
    approved = _pending(session, approval_slot, 2)
    approve_booking(session, business_id, approved.id, NOW)

    with pytest.raises(InvalidStateError):
        approve_booking(session, business_id, approved.id, NOW)
    with pytest.raises(InvalidStateError):
        reject_booking(session, business_id, approved.id, NOW)  # 確定済みは、却下できない

    # 失敗した操作で、定員が、勝手に解放されていない
    assert _booked_count(session, approval_slot.id) == 2


def test_a_rejected_booking_cannot_release_seats_twice(
    session: Session, approval_slot: Slot
) -> None:
    business_id = _business_id_of(approval_slot)
    first = _pending(session, approval_slot, 1)
    second = _pending(session, approval_slot, 2)
    reject_booking(session, business_id, first.id, NOW)

    with pytest.raises(InvalidStateError):
        reject_booking(session, business_id, first.id, NOW)
    with pytest.raises(InvalidStateError):
        approve_booking(session, business_id, first.id, NOW)

    assert _booked_count(session, approval_slot.id) == 2  # 2件目の分（2人）だけが残る
    assert second.status == BookingStatus.PENDING


def test_instant_booking_is_already_confirmed_so_it_cannot_be_approved(
    session: Session, instant_slot: Slot
) -> None:
    booking = book_slot(session, _new(instant_slot), NOW)

    with pytest.raises(InvalidStateError):
        approve_booking(session, _business_id_of(instant_slot), booking.id, NOW)


def test_another_business_cannot_approve_or_reject(session: Session, approval_slot: Slot) -> None:
    booking = _pending(session, approval_slot, 2)
    other_business_id = create_business(session, "別の事業者").id

    with pytest.raises(NotFoundError):
        approve_booking(session, other_business_id, booking.id, NOW)
    with pytest.raises(NotFoundError):
        reject_booking(session, other_business_id, booking.id, NOW)

    session.expire_all()
    assert session.get(Booking, booking.id).status == BookingStatus.PENDING  # type: ignore[union-attr]
    assert _booked_count(session, approval_slot.id) == 2


# ---- 予約の確認 ----


@pytest.mark.parametrize(
    "contact", ["09012345678", "090-1234-5678", "０９０－１２３４－５６７８", "HANAKO@example.com"]
)
def test_guest_can_find_the_booking_with_phone_or_email(
    session: Session, instant_slot: Slot, contact: str
) -> None:
    booking = book_slot(session, _new(instant_slot), NOW)

    found = find_booking_for_guest(session, booking.booking_number.lower(), contact)

    assert found.id == booking.id


def test_wrong_contact_and_unknown_number_give_the_same_not_found(
    session: Session, instant_slot: Slot
) -> None:
    booking = book_slot(session, _new(instant_slot), NOW)

    with pytest.raises(NotFoundError) as wrong_contact:
        find_booking_for_guest(session, booking.booking_number, "09099999999")
    with pytest.raises(NotFoundError) as unknown_number:
        find_booking_for_guest(session, "ZZZZZZZZZZ", PHONE)

    assert wrong_contact.value.status_code == unknown_number.value.status_code == 404
    assert wrong_contact.value.message == unknown_number.value.message
