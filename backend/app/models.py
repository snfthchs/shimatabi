"""データモデル（`docs/product/design-overview.md` の3章）。

日時はUTC・タイムゾーン付き（`UTCDateTime`）、個人情報は暗号化（`EncryptedString`）で保存する。
状態や種類の値は、文字列で保存し、CHECK制約で取りうる値を限る。
"""

import datetime
import enum

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.clock import utc_now
from app.crypto import EncryptedString
from app.db import Base, UTCDateTime


class Category(enum.StrEnum):
    """体験の種類。"""

    MARINE = "marine"  # 海
    CRAFT = "craft"  # 工芸
    NATURE = "nature"  # 自然
    FOOD = "food"  # 食


class ConfirmationMode(enum.StrEnum):
    """予約の確定方式。"""

    INSTANT = "instant"  # 空きがあれば、予約と同時に確定する
    APPROVAL = "approval"  # 事業者が承認して初めて確定する


class SlotStatus(enum.StrEnum):
    """便の状態。"""

    OPEN = "open"  # 受付中
    CANCELLED = "cancelled"  # 中止（P1）


class BookingStatus(enum.StrEnum):
    """予約の状態。"""

    PENDING = "pending"  # 承認待ち
    CONFIRMED = "confirmed"  # 確定
    REJECTED = "rejected"  # 却下
    CANCELLED = "cancelled"  # 取消（便の中止で使う。P1）


# 定員を押さえる予約の状態（承認待ちも定員に数える）
ACTIVE_BOOKING_STATUSES = (BookingStatus.PENDING, BookingStatus.CONFIRMED)


def _in_values(column: str, enum_type: type[enum.StrEnum]) -> str:
    """列の値が、列挙の値のどれかであることを確かめるCHECK制約の条件を作る。"""
    values = ", ".join(f"'{member.value}'" for member in enum_type)
    return f"{column} IN ({values})"


class Business(Base):
    """事業者。"""

    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    area: Mapped[str] = mapped_column(String(50))

    users: Mapped[list["BusinessUser"]] = relationship(back_populates="business")
    experiences: Mapped[list["Experience"]] = relationship(back_populates="business")


class BusinessUser(Base):
    """事業者の管理画面にログインするアカウント。"""

    __tablename__ = "business_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    login_id: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    business: Mapped[Business] = relationship(back_populates="users")


class LoginSession(Base):
    """ログインセッション。セッションIDではなく、そのSHA-256ハッシュを保存する（ADR 0003）。"""

    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_user_id: Mapped[int] = mapped_column(ForeignKey("business_users.id"))
    created_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime, default=utc_now)
    expires_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime)

    business_user: Mapped[BusinessUser] = relationship()


class Experience(Base):
    """体験。"""

    __tablename__ = "experiences"
    __table_args__ = (
        CheckConstraint(_in_values("category", Category), name="ck_experiences_category"),
        CheckConstraint(
            _in_values("confirmation_mode", ConfirmationMode),
            name="ck_experiences_confirmation_mode",
        ),
        CheckConstraint("price_yen >= 0", name="ck_experiences_price_yen"),
        CheckConstraint("duration_minutes > 0", name="ck_experiences_duration_minutes"),
        CheckConstraint("minutes_from_naha >= 0", name="ck_experiences_minutes_from_naha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    title: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20))
    area: Mapped[str] = mapped_column(String(50))
    meeting_point: Mapped[str] = mapped_column(Text)
    price_yen: Mapped[int] = mapped_column(Integer)  # 1人あたりの料金（円）
    duration_minutes: Mapped[int] = mapped_column(Integer)
    kids_ok: Mapped[bool] = mapped_column(Boolean)
    min_age: Mapped[int | None] = mapped_column(Integer)
    rain_ok: Mapped[bool] = mapped_column(Boolean)  # 雨でも実施できる（屋内、または雨天対応）
    minutes_from_naha: Mapped[int] = mapped_column(Integer)  # 那覇から車での目安（分）
    confirmation_mode: Mapped[str] = mapped_column(String(20))
    photo_url: Mapped[str] = mapped_column(String(255))
    map_url: Mapped[str | None] = mapped_column(String(500))  # 地図のリンク（P1）

    business: Mapped[Business] = relationship(back_populates="experiences")
    slots: Mapped[list["Slot"]] = relationship(back_populates="experience")


class Slot(Base):
    """便（ある体験の、ある日・ある時間の1回分）。"""

    __tablename__ = "slots"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_slots_capacity"),
        # 予約済み人数（承認待ち＋確定）は、0以上で、定員を超えない。
        # ダブルブッキングを防ぐ、最後の砦である。
        CheckConstraint(
            "booked_count >= 0 AND booked_count <= capacity", name="ck_slots_booked_count"
        ),
        CheckConstraint(_in_values("status", SlotStatus), name="ck_slots_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    experience_id: Mapped[int] = mapped_column(ForeignKey("experiences.id"))
    starts_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime)
    capacity: Mapped[int] = mapped_column(Integer)
    booked_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=SlotStatus.OPEN)

    experience: Mapped[Experience] = relationship(back_populates="slots")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="slot")


class Booking(Base):
    """予約。氏名・電話・メールは暗号化して保存する（検索・並べ替えには使えない）。"""

    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("party_size >= 1", name="ck_bookings_party_size"),
        CheckConstraint(_in_values("status", BookingStatus), name="ck_bookings_status"),
        Index("ix_bookings_slot_id_status", "slot_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_number: Mapped[str] = mapped_column(String(10), unique=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"))
    party_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    guest_name: Mapped[str] = mapped_column(EncryptedString)
    guest_phone: Mapped[str] = mapped_column(EncryptedString)
    guest_email: Mapped[str] = mapped_column(EncryptedString)
    created_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime, default=utc_now)
    decided_at: Mapped[datetime.datetime | None] = mapped_column(UTCDateTime)

    slot: Mapped[Slot] = relationship(back_populates="bookings")
