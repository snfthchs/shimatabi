"""テスト用のデータを作る補助関数。値は、すべて架空のものである。"""

import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.clock import JST
from app.models import (
    Booking,
    BookingStatus,
    Business,
    BusinessUser,
    Category,
    ConfirmationMode,
    Experience,
    Slot,
    SlotStatus,
)
from app.passwords import hash_password


def create_business(session: Session, name: str = "テスト事業者") -> Business:
    business = Business(name=name, area="那覇市")
    session.add(business)
    session.flush()
    return business


def create_business_user(
    session: Session,
    business: Business,
    login_id: str = "demo-owner",
    password: str = "correct-horse-battery",
) -> BusinessUser:
    user = BusinessUser(
        business_id=business.id, login_id=login_id, password_hash=hash_password(password)
    )
    session.add(user)
    session.flush()
    return user


def create_experience(session: Session, business: Business, **overrides: Any) -> Experience:
    values: dict[str, Any] = {
        "business_id": business.id,
        "title": "テスト体験",
        "summary": "テスト用の体験",
        "description": "テスト用の体験の説明",
        "category": Category.CRAFT,
        "area": "那覇市",
        "meeting_point": "テスト用の集合場所",
        "price_yen": 3000,
        "duration_minutes": 90,
        "kids_ok": True,
        "min_age": None,
        "rain_ok": True,
        "minutes_from_naha": 10,
        "confirmation_mode": ConfirmationMode.INSTANT,
        "photo_url": "/photos/test.svg",
    }
    values.update(overrides)
    experience = Experience(**values)
    session.add(experience)
    session.flush()
    return experience


def create_slot(session: Session, experience: Experience, **overrides: Any) -> Slot:
    values: dict[str, Any] = {
        "experience_id": experience.id,
        "starts_at": datetime.datetime(2030, 1, 15, 9, 0, tzinfo=JST),
        "capacity": 8,
        "booked_count": 0,
        "status": SlotStatus.OPEN,
    }
    values.update(overrides)
    slot = Slot(**values)
    session.add(slot)
    session.flush()
    return slot


def create_booking(session: Session, slot: Slot, **overrides: Any) -> Booking:
    values: dict[str, Any] = {
        "booking_number": "TESTA23456",
        "slot_id": slot.id,
        "party_size": 2,
        "status": BookingStatus.PENDING,
        "guest_name": "山田 花子",
        "guest_phone": "090-1234-5678",
        "guest_email": "hanako@example.com",
    }
    values.update(overrides)
    booking = Booking(**values)
    session.add(booking)
    session.flush()
    return booking
