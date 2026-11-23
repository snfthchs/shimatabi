from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Booking
from tests.scenario import Catalog, build_catalog

NAME = "山田 花子"
PHONE = "090-1234-5678"
EMAIL = "hanako@example.com"


@pytest.fixture
def catalog(session: Session) -> Catalog:
    return build_catalog(session)


def _body(slot_id: int, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "slot_id": slot_id,
        "party_size": 2,
        "guest_name": NAME,
        "guest_phone": PHONE,
        "guest_email": EMAIL,
    }
    body.update(overrides)
    return body


def _book(client: TestClient, slot_id: int, **overrides: Any) -> Any:
    return client.post("/api/bookings", json=_body(slot_id, **overrides))


# ---- 予約の作成 ----


def test_instant_booking_is_created_as_confirmed(client: TestClient, catalog: Catalog) -> None:
    response = _book(client, catalog.marine_today_afternoon.id)

    assert response.status_code == 201
    body = response.json()
    assert len(body["booking_number"]) == 10
    assert body["status"] == "confirmed"
    assert body["experience_title"] == "海の体験"
    assert body["starts_at"] == "2026-11-24T04:00:00Z"
    assert body["party_size"] == 2


def test_approval_booking_is_created_as_pending(client: TestClient, catalog: Catalog) -> None:
    response = _book(client, catalog.craft_tomorrow.id)

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_booking_reduces_the_remaining_seats_shown_in_the_detail(
    client: TestClient, catalog: Catalog
) -> None:
    _book(client, catalog.marine_today_afternoon.id, party_size=3)

    detail = client.get(f"/api/experiences/{catalog.marine.id}").json()
    slot = next(s for s in detail["slots"] if s["id"] == catalog.marine_today_afternoon.id)

    assert slot["remaining"] == 5  # 定員8 - 3人


def test_pending_booking_also_takes_seats(client: TestClient, catalog: Catalog) -> None:
    # 承認待ちでも、定員に数える（定員4の便に、4人の承認待ちが入ると、満席になる）
    assert _book(client, catalog.craft_tomorrow.id, party_size=4).status_code == 201

    response = _book(client, catalog.craft_tomorrow.id, party_size=1)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SLOT_UNAVAILABLE"


def test_full_slot_is_refused_with_409(client: TestClient, catalog: Catalog) -> None:
    response = _book(client, catalog.craft_today_full.id, party_size=1)

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "SLOT_UNAVAILABLE",
            "message": "この便は満席、または受付を終了しています。",
        }
    }


def test_party_larger_than_remaining_seats_is_refused(client: TestClient, catalog: Catalog) -> None:
    response = _book(client, catalog.marine_tomorrow.id, party_size=5)  # 定員4

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SLOT_UNAVAILABLE"


@pytest.mark.parametrize("slot_attribute", ["marine_past", "marine_cancelled"])
def test_past_or_cancelled_slot_is_refused(
    client: TestClient, catalog: Catalog, slot_attribute: str
) -> None:
    slot = getattr(catalog, slot_attribute)

    response = _book(client, slot.id, party_size=1)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SLOT_UNAVAILABLE"


def test_missing_slot_is_404(client: TestClient) -> None:
    response = _book(client, 99999)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ---- 入力の検証 ----


@pytest.mark.parametrize("missing", ["guest_name", "guest_phone", "guest_email", "party_size"])
def test_name_phone_and_email_are_all_required(
    client: TestClient, catalog: Catalog, missing: str
) -> None:
    body = _body(catalog.marine_today_afternoon.id)
    del body[missing]

    response = client.post("/api/bookings", json=body)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [detail["field"] for detail in error["details"]] == [missing]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"guest_name": "   "}, "guest_name"),
        ({"guest_name": "あ" * 101}, "guest_name"),
        ({"guest_phone": "INVALIDPHONE"}, "guest_phone"),
        ({"guest_phone": "123"}, "guest_phone"),
        ({"guest_email": "INVALIDEMAIL"}, "guest_email"),
        ({"guest_email": "a@b"}, "guest_email"),
        ({"party_size": 0}, "party_size"),
        ({"party_size": 51}, "party_size"),
    ],
)
def test_invalid_input_is_rejected_without_echoing_the_value(
    client: TestClient, catalog: Catalog, overrides: dict[str, Any], field: str
) -> None:
    response = _book(client, catalog.marine_today_afternoon.id, **overrides)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in [detail["field"] for detail in error["details"]]
    for value in overrides.values():
        if isinstance(value, str) and value.strip():
            assert value not in response.text  # 入力された値は、エラーに含めない


def test_input_is_normalized_before_saving(
    client: TestClient, catalog: Catalog, session: Session
) -> None:
    response = _book(
        client,
        catalog.marine_today_afternoon.id,
        guest_name=" 山田　花子 ",  # 前後の空白と、全角の空白
        guest_phone="０９０－１２３４－５６７８",  # 全角
    )

    assert response.status_code == 201
    session.expire_all()
    booking = session.query(Booking).one()
    assert booking.guest_name == "山田 花子"
    assert booking.guest_phone == "09012345678"  # 半角で、ハイフンなし


# ---- 予約の確認 ----


def _create_and_get_number(client: TestClient, catalog: Catalog) -> str:
    response = _book(client, catalog.marine_today_afternoon.id)
    assert response.status_code == 201
    return str(response.json()["booking_number"])


def test_lookup_with_phone_returns_status_without_personal_info(
    client: TestClient, catalog: Catalog
) -> None:
    number = _create_and_get_number(client, catalog)

    response = client.post(
        "/api/bookings/lookup", json={"booking_number": number, "contact": PHONE}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["booking_number"] == number
    assert body["status"] == "confirmed"
    assert body["experience_title"] == "海の体験"
    assert body["party_size"] == 2
    assert body["meeting_point"]
    assert response.headers["cache-control"] == "no-store"
    for personal_info in (NAME, "山田", PHONE, "09012345678", EMAIL):
        assert personal_info not in response.text  # 個人情報は、返さない


@pytest.mark.parametrize(
    "contact", [EMAIL, "HANAKO@Example.com", "09012345678", "０９０１２３４５６７８"]
)
def test_lookup_accepts_the_contact_in_any_writing(
    client: TestClient, catalog: Catalog, contact: str
) -> None:
    number = _create_and_get_number(client, catalog)

    response = client.post(
        "/api/bookings/lookup", json={"booking_number": number.lower(), "contact": contact}
    )

    assert response.status_code == 200


def test_wrong_contact_and_unknown_number_look_the_same(
    client: TestClient, catalog: Catalog
) -> None:
    number = _create_and_get_number(client, catalog)

    wrong_contact = client.post(
        "/api/bookings/lookup", json={"booking_number": number, "contact": "09099999999"}
    )
    unknown_number = client.post(
        "/api/bookings/lookup", json={"booking_number": "ZZZZZZZZZZ", "contact": PHONE}
    )

    assert wrong_contact.status_code == unknown_number.status_code == 404
    assert wrong_contact.json() == unknown_number.json()
    assert wrong_contact.json()["error"]["code"] == "NOT_FOUND"


def test_lookup_needs_both_number_and_contact(client: TestClient) -> None:
    response = client.post("/api/bookings/lookup", json={"booking_number": "ABCDE23456"})

    assert response.status_code == 422


def test_lookup_is_post_only_so_the_contact_never_appears_in_the_url(client: TestClient) -> None:
    response = client.get("/api/bookings/lookup", params={"booking_number": "A", "contact": PHONE})

    assert response.status_code in (404, 405, 422)
    assert response.status_code != 200
