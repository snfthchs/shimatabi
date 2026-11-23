"""予約の作成・承認・却下・確認（`docs/product/design-overview.md` の3.4節）。

ダブルブッキングを防ぐため、定員の更新は、行ロックに頼らず、**条件付きUPDATE**で行う
（ADR 0002）。「条件に合うときだけ更新し、更新された行数（rowcount）で成否を判定する」。
判定と更新が1回の命令で終わるので、同時に来たリクエストでも、定員を超えない。

SQLiteでは、トランザクションの最初の書き込みで、ほかの書き込みを待つ。そのため、
どの処理も、**最初の書き込みを、この条件付きUPDATEにしている**（読み取りは、その前に済ませる）。
SQLiteの `SAVEPOINT` には癖があるので使わず、予約番号が重複したときは、
トランザクション全体をやり直す。
"""

import datetime
import secrets
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult, Result
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.contact import contact_matches, normalize_booking_number
from app.errors import InvalidStateError, NotFoundError, SlotUnavailableError
from app.models import Booking, BookingStatus, ConfirmationMode, Slot, SlotStatus
from app.scoping import get_booking_or_404

# 予約番号に使う文字（紛らわしい0・1・I・Oを除いた32種）と、長さ
BOOKING_NUMBER_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
BOOKING_NUMBER_LENGTH = 10

# 予約番号が重複したときの、やり直しの上限（32^10 通りあるので、実際には、ほぼ起きない）
MAX_BOOKING_NUMBER_ATTEMPTS = 3


def _matched_rows(result: Result[Any]) -> int:
    """UPDATEの `WHERE` に一致した行数（rowcount）。値が変わったかどうかではなく、一致した数。"""
    if not isinstance(result, CursorResult):
        raise TypeError("UPDATE の結果ではありません。")
    return int(result.rowcount)


def generate_booking_number() -> str:
    """予約番号を作る（暗号論的な乱数。推測されにくい）。"""
    return "".join(secrets.choice(BOOKING_NUMBER_ALPHABET) for _ in range(BOOKING_NUMBER_LENGTH))


@dataclass(frozen=True)
class NewBooking:
    """予約の申し込み。氏名・電話・メールは、検証して書き方をそろえたあとの値。"""

    slot_id: int
    party_size: int
    guest_name: str
    guest_phone: str
    guest_email: str


def create_booking(session: Session, new: NewBooking, now: datetime.datetime) -> Booking:
    """予約を作る。

    1. 便を、条件付きUPDATEで押さえる（受付中・開始前・加算後の人数が定員以下のときだけ）。
       更新された行が0なら、予約は作らず、`SlotUnavailableError`（409）にする。
    2. 予約を作る。即時確定の体験は `confirmed`、承認制の体験は `pending`。
       承認待ちも、定員に数える。
    1と2は、1つのトランザクション。途中で失敗したら、ロールバックで、定員も元に戻る。
    """
    slot = session.get(Slot, new.slot_id)
    if slot is None:
        raise NotFoundError("便が見つかりません。")
    is_instant = slot.experience.confirmation_mode == ConfirmationMode.INSTANT
    status = BookingStatus.CONFIRMED if is_instant else BookingStatus.PENDING

    for _ in range(MAX_BOOKING_NUMBER_ATTEMPTS):
        reserved = session.execute(
            update(Slot)
            .where(
                Slot.id == new.slot_id,
                Slot.status == SlotStatus.OPEN,
                Slot.starts_at > now,
                Slot.booked_count + new.party_size <= Slot.capacity,
            )
            .values(booked_count=Slot.booked_count + new.party_size)
            .execution_options(synchronize_session=False)
        )
        if _matched_rows(reserved) == 0:
            session.rollback()
            raise SlotUnavailableError()

        booking = Booking(
            booking_number=generate_booking_number(),
            slot_id=new.slot_id,
            party_size=new.party_size,
            status=status,
            guest_name=new.guest_name,
            guest_phone=new.guest_phone,
            guest_email=new.guest_email,
            created_at=now,
        )
        session.add(booking)
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            if "booking_number" not in str(error.orig):
                raise  # 予約番号の重複ではない、別の制約の違反は、隠さない
            continue  # 予約番号の重複。定員の更新も含めて、最初からやり直す
        session.expire(slot)  # 定員を、条件付きUPDATEで更新したので、保持している値を捨てる
        return booking
    raise RuntimeError("予約番号を作れませんでした。")


def approve_booking(
    session: Session, business_id: int, booking_id: int, now: datetime.datetime
) -> Booking:
    """承認待ちの予約を、承認する（`confirmed` にする）。定員は、作成時に押さえてあるので変えない。

    他の事業者の予約と、存在しない予約は、404。すでに処理した予約は、`InvalidStateError`（409）。
    """
    booking = get_booking_or_404(session, business_id, booking_id)
    changed = session.execute(
        update(Booking)
        .where(Booking.id == booking.id, Booking.status == BookingStatus.PENDING)
        .values(status=BookingStatus.CONFIRMED, decided_at=now)
        .execution_options(synchronize_session=False)
    )
    if _matched_rows(changed) == 0:
        session.rollback()
        raise InvalidStateError()
    session.commit()
    session.refresh(booking)
    return booking


def reject_booking(
    session: Session, business_id: int, booking_id: int, now: datetime.datetime
) -> Booking:
    """承認待ちの予約を、却下する（`rejected` にする）。押さえていた定員を、解放する。

    予約の更新と、定員の解放は、1つのトランザクションで行う。
    """
    booking = get_booking_or_404(session, business_id, booking_id)
    party_size = booking.party_size
    changed = session.execute(
        update(Booking)
        .where(Booking.id == booking.id, Booking.status == BookingStatus.PENDING)
        .values(status=BookingStatus.REJECTED, decided_at=now)
        .execution_options(synchronize_session=False)
    )
    if _matched_rows(changed) == 0:
        session.rollback()
        raise InvalidStateError()
    released = session.execute(
        update(Slot)
        .where(Slot.id == booking.slot_id, Slot.booked_count >= party_size)
        .values(booked_count=Slot.booked_count - party_size)
        .execution_options(synchronize_session=False)
    )
    if _matched_rows(released) == 0:
        # 承認待ちの予約があるのに、定員が足りない。整合性が崩れているので、隠さない。
        session.rollback()
        raise RuntimeError("定員の整合性が取れていません。")
    session.commit()
    session.refresh(booking)
    return booking


def find_booking_for_guest(session: Session, booking_number: str, contact: str) -> Booking:
    """予約番号と連絡先（電話またはメール）が一致する予約を返す。

    予約番号が存在しない場合も、連絡先が違う場合も、同じ404にする（番号の存在を推測させない）。
    """
    booking = session.scalar(
        select(Booking).where(Booking.booking_number == normalize_booking_number(booking_number))
    )
    if booking is None or not contact_matches(
        contact, phone=booking.guest_phone, email=booking.guest_email
    ):
        raise NotFoundError("予約が見つかりません。")
    return booking
