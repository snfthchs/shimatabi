"""事業者向け: 便と予約の管理（`/api/admin`）。要ログイン。自社のデータだけを対象にする。

他の事業者のデータは、存在しないもの（404）として扱う（`app.scoping`）。
予約の一覧は、氏名・電話・メールを、サーバー側でマスクして返す（ADR 0004）。
平文の連絡先は、「連絡先を表示」にあたる `.../contact` だけが返す。
"""

import datetime

from fastapi import APIRouter, Response
from sqlalchemy import func, select
from sqlalchemy.orm import contains_eager

from app.clock import jst_day_range
from app.deps import CurrentUserDep, NowDep, SessionDep
from app.masking import mask_email, mask_name, mask_phone
from app.models import ACTIVE_BOOKING_STATUSES, Booking, BookingStatus, Slot
from app.schemas import AdminBookingOut, AdminSlotOut, ContactOut
from app.scoping import business_bookings, business_slots, get_booking_or_404
from app.services.bookings import approve_booking, reject_booking

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _no_store(response: Response) -> None:
    # 予約の情報は、ブラウザや中継のキャッシュに残さない。
    response.headers["Cache-Control"] = "no-store"


def _booking_out(booking: Booking) -> AdminBookingOut:
    slot = booking.slot
    return AdminBookingOut(
        id=booking.id,
        booking_number=booking.booking_number,
        status=booking.status,
        party_size=booking.party_size,
        created_at=booking.created_at,
        decided_at=booking.decided_at,
        slot_id=slot.id,
        starts_at=slot.starts_at,
        experience_title=slot.experience.title,
        guest_name=mask_name(booking.guest_name),
        guest_phone=mask_phone(booking.guest_phone),
        guest_email=mask_email(booking.guest_email),
    )


@router.get("/slots", response_model=list[AdminSlotOut])
def list_slots(
    user: CurrentUserDep,
    session: SessionDep,
    response: Response,
    date: datetime.date | None = None,
) -> list[AdminSlotOut]:
    """自社の便の一覧と、便ごとの予約の状況（承認待ち・確定の人数）。`date` は日本時間の日付。"""
    statement = (
        business_slots(user.business_id)
        .options(contains_eager(Slot.experience))
        .order_by(Slot.starts_at, Slot.id)
    )
    if date is not None:
        start, end = jst_day_range(date)
        statement = statement.where(Slot.starts_at >= start, Slot.starts_at < end)
    slots = list(session.scalars(statement))

    # 人数は、SQLの集計で出す（暗号化した個人情報の列は、読まない・復号しない）。
    rows = session.execute(
        select(Booking.slot_id, Booking.status, func.sum(Booking.party_size))
        .where(
            Booking.slot_id.in_([slot.id for slot in slots]),
            Booking.status.in_([status.value for status in ACTIVE_BOOKING_STATUSES]),
        )
        .group_by(Booking.slot_id, Booking.status)
    ).all()
    counts = {(slot_id, status): int(total) for slot_id, status, total in rows}

    _no_store(response)
    return [
        AdminSlotOut(
            id=slot.id,
            experience_id=slot.experience_id,
            experience_title=slot.experience.title,
            starts_at=slot.starts_at,
            capacity=slot.capacity,
            booked_count=slot.booked_count,
            pending_count=counts.get((slot.id, BookingStatus.PENDING.value), 0),
            confirmed_count=counts.get((slot.id, BookingStatus.CONFIRMED.value), 0),
            status=slot.status,
        )
        for slot in slots
    ]


@router.get("/bookings", response_model=list[AdminBookingOut])
def list_bookings(
    user: CurrentUserDep,
    session: SessionDep,
    response: Response,
    status: BookingStatus | None = None,
    slot_id: int | None = None,
    date: datetime.date | None = None,
) -> list[AdminBookingOut]:
    """自社の予約の一覧（マスク済み）。便の開始が早い順、申し込みが早い順に並べる。"""
    statement = (
        business_bookings(user.business_id)
        .options(contains_eager(Booking.slot).contains_eager(Slot.experience))
        .order_by(Slot.starts_at, Booking.created_at, Booking.id)
    )
    if status is not None:
        statement = statement.where(Booking.status == status.value)
    if slot_id is not None:
        statement = statement.where(Booking.slot_id == slot_id)
    if date is not None:
        start, end = jst_day_range(date)
        statement = statement.where(Slot.starts_at >= start, Slot.starts_at < end)

    _no_store(response)
    return [_booking_out(booking) for booking in session.scalars(statement)]


@router.post("/bookings/{booking_id}/approve", response_model=AdminBookingOut)
def approve(
    booking_id: int,
    user: CurrentUserDep,
    session: SessionDep,
    now: NowDep,
    response: Response,
) -> AdminBookingOut:
    """承認待ちの予約を承認する。すでに処理した予約は、409（INVALID_STATE）。"""
    booking = approve_booking(session, user.business_id, booking_id, now)
    _no_store(response)
    return _booking_out(booking)


@router.post("/bookings/{booking_id}/reject", response_model=AdminBookingOut)
def reject(
    booking_id: int,
    user: CurrentUserDep,
    session: SessionDep,
    now: NowDep,
    response: Response,
) -> AdminBookingOut:
    """承認待ちの予約を却下して、定員を解放する。すでに処理した予約は、409（INVALID_STATE）。"""
    booking = reject_booking(session, user.business_id, booking_id, now)
    _no_store(response)
    return _booking_out(booking)


@router.get("/bookings/{booking_id}/contact", response_model=ContactOut)
def get_contact(
    booking_id: int,
    user: CurrentUserDep,
    session: SessionDep,
    response: Response,
) -> ContactOut:
    """予約1件の、氏名・電話・メールを、平文で返す（「連絡先を表示」）。"""
    booking = get_booking_or_404(session, user.business_id, booking_id)
    _no_store(response)
    return ContactOut(
        guest_name=booking.guest_name,
        guest_phone=booking.guest_phone,
        guest_email=booking.guest_email,
    )
