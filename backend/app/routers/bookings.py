"""旅行者向け: 予約の作成と確認（`/api/bookings`）。認証は不要（ゲスト予約）。"""

from fastapi import APIRouter, Response

from app.deps import NowDep, SessionDep
from app.models import Booking
from app.schemas import BookingCreate, BookingCreated, BookingLookup, BookingStatusOut
from app.services.bookings import NewBooking, create_booking, find_booking_for_guest

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("", status_code=201, response_model=BookingCreated)
def create(body: BookingCreate, session: SessionDep, now: NowDep) -> BookingCreated:
    """予約を作る。即時確定の体験は確定、承認制の体験は承認待ちになる。"""
    booking = create_booking(
        session,
        NewBooking(
            slot_id=body.slot_id,
            party_size=body.party_size,
            guest_name=body.guest_name,
            guest_phone=body.guest_phone,
            guest_email=body.guest_email,
        ),
        now,
    )
    return BookingCreated(
        booking_number=booking.booking_number,
        status=booking.status,
        experience_title=booking.slot.experience.title,
        starts_at=booking.slot.starts_at,
        party_size=booking.party_size,
    )


def _status_out(booking: Booking) -> BookingStatusOut:
    return BookingStatusOut(
        booking_number=booking.booking_number,
        status=booking.status,
        experience_title=booking.slot.experience.title,
        starts_at=booking.slot.starts_at,
        party_size=booking.party_size,
        meeting_point=booking.slot.experience.meeting_point,
    )


# 連絡先は個人情報なので、URLやクエリではなく、POSTの本文で送る。
@router.post("/lookup", response_model=BookingStatusOut)
def lookup(body: BookingLookup, session: SessionDep, response: Response) -> BookingStatusOut:
    """予約番号と連絡先（電話またはメール）で、予約の状態を確認する。"""
    booking = find_booking_for_guest(session, body.booking_number, body.contact)
    response.headers["Cache-Control"] = "no-store"
    return _status_out(booking)
