from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import BookingStatus, ConfirmationMode
from tests.api_helpers import DEFAULT_PASSWORD, log_in
from tests.factories import (
    create_booking,
    create_business,
    create_business_user,
    create_experience,
    create_slot,
)
from tests.scenario import at

NAME = "山田 花子"
PHONE = "090-1234-5678"
EMAIL = "hanako@example.com"


@dataclass
class World:
    """事業者A・Bと、それぞれの便・予約（IDを控える）。"""

    slot_a: int
    slot_a_later: int
    pending_a: int  # Aの承認待ち（2人）
    confirmed_a: int  # Aの確定（1人）
    slot_b: int
    pending_b: int  # Bの承認待ち（2人）


@pytest.fixture
def world(session: Session) -> World:
    business_a = create_business(session, "事業者A")
    business_b = create_business(session, "事業者B")
    create_business_user(session, business_a, login_id="owner-a", password=DEFAULT_PASSWORD)
    create_business_user(session, business_b, login_id="owner-b", password=DEFAULT_PASSWORD)
    experience_a = create_experience(
        session, business_a, title="A体験", confirmation_mode=ConfirmationMode.APPROVAL
    )
    experience_b = create_experience(
        session, business_b, title="B体験", confirmation_mode=ConfirmationMode.APPROVAL
    )

    slot_a = create_slot(session, experience_a, starts_at=at(1, 10), capacity=6, booked_count=3)
    slot_a_later = create_slot(session, experience_a, starts_at=at(2, 10), capacity=6)
    slot_b = create_slot(session, experience_b, starts_at=at(1, 11), capacity=4, booked_count=2)

    pending_a = create_booking(
        session,
        slot_a,
        booking_number="PENDA23456",
        party_size=2,
        status=BookingStatus.PENDING,
        guest_name=NAME,
        guest_phone=PHONE,
        guest_email=EMAIL,
    )
    confirmed_a = create_booking(
        session,
        slot_a,
        booking_number="CONFA23456",
        party_size=1,
        status=BookingStatus.CONFIRMED,
        guest_name="佐藤 次郎",
        guest_phone="080-9876-5432",
        guest_email="jiro.sato@example.com",
    )
    pending_b = create_booking(
        session,
        slot_b,
        booking_number="PENDB23456",
        party_size=2,
        status=BookingStatus.PENDING,
        guest_name="鈴木 美咲",
        guest_phone="070-1111-2222",
        guest_email="misaki@example.com",
    )
    session.commit()
    return World(
        slot_a=slot_a.id,
        slot_a_later=slot_a_later.id,
        pending_a=pending_a.id,
        confirmed_a=confirmed_a.id,
        slot_b=slot_b.id,
        pending_b=pending_b.id,
    )


# ---- 認証 ----


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/admin/slots"),
        ("GET", "/api/admin/bookings"),
        ("POST", "/api/admin/bookings/1/approve"),
        ("POST", "/api/admin/bookings/1/reject"),
        ("GET", "/api/admin/bookings/1/contact"),
    ],
)
def test_all_admin_endpoints_require_login(
    client: TestClient, world: World, method: str, path: str
) -> None:
    response = client.request(method, path)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


# ---- 一覧 ----


def test_bookings_list_is_scoped_and_masked(client: TestClient, world: World) -> None:
    log_in(client, "owner-a")

    response = client.get("/api/admin/bookings")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    bookings = response.json()
    assert [b["id"] for b in bookings] == [world.pending_a, world.confirmed_a]  # 自社だけ
    first = bookings[0]
    assert first["booking_number"] == "PENDA23456"
    assert first["status"] == "pending"
    assert first["experience_title"] == "A体験"
    assert first["guest_name"] == "山***"
    assert first["guest_phone"] == "090-****-5678"
    assert first["guest_email"] == "h***@example.com"
    # 平文は、レスポンスのどこにも含まれない（他社の予約者の情報も、含まれない）
    for personal_info in (NAME, "山田", PHONE, EMAIL, "佐藤", "jiro.sato", "鈴木", "misaki"):
        assert personal_info not in response.text


def test_bookings_list_filters(client: TestClient, world: World) -> None:
    log_in(client, "owner-a")

    pending = client.get("/api/admin/bookings", params={"status": "pending"}).json()
    confirmed = client.get("/api/admin/bookings", params={"status": "confirmed"}).json()
    by_slot = client.get("/api/admin/bookings", params={"slot_id": world.slot_a}).json()
    other_slot = client.get("/api/admin/bookings", params={"slot_id": world.slot_a_later}).json()
    by_date = client.get("/api/admin/bookings", params={"date": "2026-11-25"}).json()
    other_date = client.get("/api/admin/bookings", params={"date": "2026-11-30"}).json()

    assert [b["id"] for b in pending] == [world.pending_a]
    assert [b["id"] for b in confirmed] == [world.confirmed_a]
    assert len(by_slot) == 2
    assert other_slot == []
    assert len(by_date) == 2
    assert other_date == []


def test_bookings_list_cannot_be_used_to_see_another_businesss_slot(
    client: TestClient, world: World
) -> None:
    log_in(client, "owner-a")

    # Bの便を指定しても、Aの予約として何も見えない（エラーにはならず、空になる）
    assert client.get("/api/admin/bookings", params={"slot_id": world.slot_b}).json() == []


def test_invalid_status_filter_is_a_validation_error(client: TestClient, world: World) -> None:
    log_in(client, "owner-a")

    response = client.get("/api/admin/bookings", params={"status": "unknown"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_slots_list_shows_counts_and_only_own_slots(client: TestClient, world: World) -> None:
    log_in(client, "owner-a")

    response = client.get("/api/admin/slots")

    assert response.status_code == 200
    slots = response.json()
    assert [s["id"] for s in slots] == [world.slot_a, world.slot_a_later]
    first = slots[0]
    assert first["experience_title"] == "A体験"
    assert (first["capacity"], first["booked_count"]) == (6, 3)
    assert (first["pending_count"], first["confirmed_count"]) == (2, 1)
    assert slots[1]["pending_count"] == slots[1]["confirmed_count"] == 0
    assert client.get("/api/admin/slots", params={"date": "2026-11-26"}).json()[0]["id"] == (
        world.slot_a_later
    )


# ---- 承認・却下 ----


def test_approve_confirms_the_booking(client: TestClient, world: World) -> None:
    log_in(client, "owner-a")

    response = client.post(f"/api/admin/bookings/{world.pending_a}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["decided_at"] is not None
    assert body["guest_name"] == "山***"  # 承認の応答も、マスク済み
    slot = client.get("/api/admin/slots").json()[0]
    assert (slot["booked_count"], slot["pending_count"], slot["confirmed_count"]) == (3, 0, 3)


def test_reject_releases_the_seats(client: TestClient, world: World) -> None:
    log_in(client, "owner-a")

    response = client.post(f"/api/admin/bookings/{world.pending_a}/reject")

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    slot = client.get("/api/admin/slots").json()[0]
    assert (slot["booked_count"], slot["pending_count"], slot["confirmed_count"]) == (1, 0, 1)


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_processed_booking_cannot_be_processed_again(
    client: TestClient, world: World, action: str
) -> None:
    log_in(client, "owner-a")
    client.post(f"/api/admin/bookings/{world.pending_a}/approve")

    response = client.post(f"/api/admin/bookings/{world.pending_a}/{action}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"
    slot = client.get("/api/admin/slots").json()[0]
    assert slot["booked_count"] == 3  # 失敗した操作で、定員は変わらない


def test_a_confirmed_booking_cannot_be_rejected(client: TestClient, world: World) -> None:
    log_in(client, "owner-a")

    response = client.post(f"/api/admin/bookings/{world.confirmed_a}/reject")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"


# ---- 連絡先の表示 ----


def test_contact_returns_the_plain_personal_info(client: TestClient, world: World) -> None:
    log_in(client, "owner-a")

    response = client.get(f"/api/admin/bookings/{world.pending_a}/contact")

    assert response.status_code == 200
    assert response.json() == {"guest_name": NAME, "guest_phone": PHONE, "guest_email": EMAIL}
    assert response.headers["cache-control"] == "no-store"


# ---- 認可（他の事業者の予約） ----


@pytest.mark.parametrize(
    ("method", "action"),
    [("POST", "approve"), ("POST", "reject"), ("GET", "contact")],
)
def test_another_businesss_booking_is_404_like_a_missing_one(
    client: TestClient, world: World, method: str, action: str
) -> None:
    log_in(client, "owner-a")

    other = client.request(method, f"/api/admin/bookings/{world.pending_b}/{action}")
    missing = client.request(method, f"/api/admin/bookings/99999/{action}")

    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()
    assert other.json()["error"]["code"] == "NOT_FOUND"


def test_another_businesss_booking_is_left_untouched(
    client: TestClient, world: World, session: Session
) -> None:
    log_in(client, "owner-a")
    client.post(f"/api/admin/bookings/{world.pending_b}/approve")
    client.post(f"/api/admin/bookings/{world.pending_b}/reject")

    log_in(client, "owner-b")
    bookings: list[dict[str, Any]] = client.get("/api/admin/bookings").json()

    assert [(b["id"], b["status"]) for b in bookings] == [(world.pending_b, "pending")]
    assert client.get("/api/admin/slots").json()[0]["booked_count"] == 2  # 定員も、そのまま


def test_each_business_sees_only_its_own_data(client: TestClient, world: World) -> None:
    log_in(client, "owner-b")

    bookings = client.get("/api/admin/bookings").json()
    slots = client.get("/api/admin/slots").json()

    assert [b["id"] for b in bookings] == [world.pending_b]
    assert [s["id"] for s in slots] == [world.slot_b]
    assert bookings[0]["guest_name"] == "鈴***"
