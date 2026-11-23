"""定員の同時実行のテスト（ダブルブッキングを起こさないことの確認）。

複数のスレッドが、それぞれ自分のDBセッションで、同時に予約を申し込む。
どんな順番で処理されても、定員を超えず、結果が食い違わないことを確かめる。
"""

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.clock import utc_now
from app.db import make_session_factory
from app.errors import InvalidStateError, SlotUnavailableError
from app.models import Booking, BookingStatus, ConfirmationMode, Slot
from app.services.bookings import NewBooking, approve_booking, reject_booking
from app.services.bookings import create_booking as book_slot
from tests.factories import create_booking, create_business, create_experience, create_slot


def _run_at_the_same_time(count: int, task: Callable[[int], str]) -> list[str]:
    """`count` 個のスレッドが、そろってから、いっせいに `task` を始める。"""
    barrier = threading.Barrier(count)

    def wrapped(index: int) -> str:
        barrier.wait()
        return task(index)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(wrapped, range(count)))


def _create_slot(
    factory: sessionmaker[Session], capacity: int, mode: ConfirmationMode
) -> tuple[int, int]:
    """体験と便を作る。(便のID, 事業者のID) を返す。"""
    with factory() as session:
        business = create_business(session)
        experience = create_experience(session, business, confirmation_mode=mode)
        slot = create_slot(session, experience, capacity=capacity)
        session.commit()
        return slot.id, business.id


def _book_task(
    factory: sessionmaker[Session], slot_id: int, party_size: int
) -> Callable[[int], str]:
    def task(index: int) -> str:
        with factory() as session:
            try:
                book_slot(
                    session,
                    NewBooking(
                        slot_id=slot_id,
                        party_size=party_size,
                        guest_name=f"テスト{index}",
                        guest_phone="09012345678",
                        guest_email=f"guest{index}@example.com",
                    ),
                    utc_now(),
                )
            except SlotUnavailableError:
                return "full"
            return "ok"

    return task


def _totals(factory: sessionmaker[Session], slot_id: int) -> tuple[int, int, int]:
    """(便の予約済み人数, 予約の件数, 予約の人数の合計) を、DBから読み直す。"""
    with factory() as session:
        slot = session.get(Slot, slot_id)
        assert slot is not None
        count, people = session.execute(
            select(func.count(), func.coalesce(func.sum(Booking.party_size), 0)).where(
                Booking.slot_id == slot_id
            )
        ).one()
        return slot.booked_count, int(count), int(people)


def test_ten_simultaneous_bookings_never_exceed_the_capacity(engine: Engine) -> None:
    factory = make_session_factory(engine)
    slot_id, _ = _create_slot(factory, capacity=3, mode=ConfirmationMode.INSTANT)

    results = _run_at_the_same_time(10, _book_task(factory, slot_id, party_size=1))

    # 定員3に、10人が同時に申し込む。成功はちょうど3件で、残りは満席として断られる。
    assert results.count("ok") == 3
    assert results.count("full") == 7
    booked_count, booking_count, people = _totals(factory, slot_id)
    assert booked_count == 3
    assert booking_count == 3
    assert people == 3


def test_parties_that_do_not_fit_are_refused_even_when_seats_remain(engine: Engine) -> None:
    factory = make_session_factory(engine)
    slot_id, _ = _create_slot(factory, capacity=5, mode=ConfirmationMode.APPROVAL)

    results = _run_at_the_same_time(6, _book_task(factory, slot_id, party_size=2))

    # 定員5に、2人組が6組。入れるのは2組（4人）。残り1席に、2人組は入れない。
    assert results.count("ok") == 2
    assert results.count("full") == 4
    booked_count, booking_count, people = _totals(factory, slot_id)
    assert booked_count == people == 4
    assert booking_count == 2
    assert booked_count <= 5


def test_simultaneous_approval_and_rejection_apply_only_once(engine: Engine) -> None:
    factory = make_session_factory(engine)

    for round_number in range(5):
        slot_id, business_id = _create_slot(factory, capacity=4, mode=ConfirmationMode.APPROVAL)
        with factory() as session:
            slot = session.get(Slot, slot_id)
            assert slot is not None
            booking = create_booking(
                session,
                slot,
                booking_number=f"RACE{round_number}23456",
                party_size=3,
                status=BookingStatus.PENDING,
            )
            slot.booked_count = 3
            session.commit()
            booking_id = booking.id

        def decide(index: int, business_id: int = business_id, booking_id: int = booking_id) -> str:
            with factory() as session:
                try:
                    if index == 0:
                        approve_booking(session, business_id, booking_id, utc_now())
                        return "approved"
                    reject_booking(session, business_id, booking_id, utc_now())
                    return "rejected"
                except InvalidStateError:
                    return "refused"

        results = _run_at_the_same_time(2, decide)

        # 承認と却下が同時に来ても、片方だけが成功し、もう片方は断られる。
        assert sorted(results) in (["approved", "refused"], ["refused", "rejected"])
        booked_count, _, _ = _totals(factory, slot_id)
        with factory() as session:
            final = session.get(Booking, booking_id)
            assert final is not None
            if final.status == BookingStatus.CONFIRMED:
                assert booked_count == 3  # 承認: 定員は、押さえたまま
            else:
                assert final.status == BookingStatus.REJECTED
                assert booked_count == 0  # 却下: 定員が、1回だけ解放される


def test_simultaneous_approvals_apply_only_once(engine: Engine) -> None:
    factory = make_session_factory(engine)
    slot_id, business_id = _create_slot(factory, capacity=4, mode=ConfirmationMode.APPROVAL)
    with factory() as session:
        slot = session.get(Slot, slot_id)
        assert slot is not None
        booking = create_booking(session, slot, booking_number="TWICE23456", party_size=2)
        slot.booked_count = 2
        session.commit()
        booking_id = booking.id

    def approve(_: int) -> str:
        with factory() as session:
            try:
                approve_booking(session, business_id, booking_id, utc_now())
            except InvalidStateError:
                return "refused"
            return "approved"

    results = _run_at_the_same_time(5, approve)

    assert results.count("approved") == 1
    assert results.count("refused") == 4
