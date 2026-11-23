"""ログイン中の事業者のデータだけに絞る、共通の条件の作り方（認可）。

事業者向けのAPIは、予約・便・体験を取り出すとき、必ずここの関数を使う。
他の事業者のデータは、「存在しないもの」（404）として扱う。存在はするが見られない、
という情報を、他の事業者に漏らさないため。

予約と便は、体験を通じて事業者につながる（予約 → 便 → 体験 → 事業者）。
"""

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import Booking, Experience, Slot


def business_experiences(business_id: int) -> Select[Experience]:
    """事業者の体験だけを取り出す検索。"""
    return select(Experience).where(Experience.business_id == business_id)


def business_slots(business_id: int) -> Select[Slot]:
    """事業者の便だけを取り出す検索。"""
    return (
        select(Slot)
        .join(Experience, Slot.experience_id == Experience.id)
        .where(Experience.business_id == business_id)
    )


def business_bookings(business_id: int) -> Select[Booking]:
    """事業者の予約だけを取り出す検索。"""
    return (
        select(Booking)
        .join(Slot, Booking.slot_id == Slot.id)
        .join(Experience, Slot.experience_id == Experience.id)
        .where(Experience.business_id == business_id)
    )


def get_booking_or_404(session: Session, business_id: int, booking_id: int) -> Booking:
    """事業者の予約を1件取り出す。他の事業者の予約と、存在しない予約は、どちらも404にする。"""
    booking = session.scalar(business_bookings(business_id).where(Booking.id == booking_id))
    if booking is None:
        raise NotFoundError()
    return booking


def get_slot_or_404(session: Session, business_id: int, slot_id: int) -> Slot:
    """事業者の便を1件取り出す。他の事業者の便と、存在しない便は、どちらも404にする。"""
    slot = session.scalar(business_slots(business_id).where(Slot.id == slot_id))
    if slot is None:
        raise NotFoundError()
    return slot
