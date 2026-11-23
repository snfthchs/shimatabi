"""ログイン（認証）と、自社のデータだけに絞る仕組み（認可）を、組み合わせて確かめる。

事業者向けの予約のAPIは Issue D で作る。ここでは、同じ部品（`CurrentUserDep` と
`app.scoping`）を使う、テスト用の小さなAPIで確かめる。
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME
from app.db import make_session_factory
from app.deps import CurrentUserDep, SessionDep, get_now, get_session_factory
from app.errors import install_error_handlers
from app.scoping import get_booking_or_404
from tests.factories import (
    create_booking,
    create_business,
    create_business_user,
    create_experience,
    create_slot,
)
from tests.fakes import FakeClock

PASSWORD = "correct-horse-battery"


@pytest.fixture
def booking_ids(session: Session) -> dict[str, int]:
    """事業者A・Bのアカウントと、それぞれの予約を作る。予約のIDを返す。"""
    ids: dict[str, int] = {}
    for key, name in (("a", "事業者A"), ("b", "事業者B")):
        business = create_business(session, name)
        create_business_user(session, business, login_id=f"owner-{key}", password=PASSWORD)
        slot = create_slot(session, create_experience(session, business))
        booking = create_booking(session, slot, booking_number=f"TEST{key.upper()}23456")
        ids[key] = booking.id
    session.commit()
    return ids


@pytest.fixture
def probe(engine: Engine, clock: FakeClock) -> Iterator[TestClient]:
    """予約を1件返すだけの、テスト用のAPI。本物のAPIと同じ部品を使う。"""
    probe_app = FastAPI()
    install_error_handlers(probe_app)
    factory = make_session_factory(engine)
    probe_app.dependency_overrides[get_session_factory] = lambda: factory
    probe_app.dependency_overrides[get_now] = lambda: clock.now

    @probe_app.get("/probe/bookings/{booking_id}")
    def read_booking(booking_id: int, user: CurrentUserDep, session: SessionDep) -> dict[str, int]:
        booking = get_booking_or_404(session, user.business_id, booking_id)
        return {"id": booking.id}

    yield TestClient(probe_app)


def _log_in_as(client: TestClient, probe: TestClient, login_id: str) -> None:
    """本物のログインAPIでログインして、そのCookieを、テスト用のAPIのクライアントに渡す。"""
    response = client.post("/api/admin/login", json={"login_id": login_id, "password": PASSWORD})
    assert response.status_code == 200
    token = client.cookies.get(SESSION_COOKIE_NAME)
    assert token is not None
    probe.cookies.set(SESSION_COOKIE_NAME, token)


def test_not_logged_in_is_401(probe: TestClient, booking_ids: dict[str, int]) -> None:
    response = probe.get(f"/probe/bookings/{booking_ids['a']}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_a_business_can_read_its_own_booking(
    client: TestClient, probe: TestClient, booking_ids: dict[str, int]
) -> None:
    _log_in_as(client, probe, "owner-a")

    response = probe.get(f"/probe/bookings/{booking_ids['a']}")

    assert response.status_code == 200
    assert response.json() == {"id": booking_ids["a"]}


def test_a_business_cannot_see_another_businesses_booking(
    client: TestClient, probe: TestClient, booking_ids: dict[str, int]
) -> None:
    _log_in_as(client, probe, "owner-a")

    other = probe.get(f"/probe/bookings/{booking_ids['b']}")
    missing = probe.get("/probe/bookings/99999")

    # 他社の予約は、存在しない予約と同じ404になる
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()
    assert other.json()["error"]["code"] == "NOT_FOUND"


def test_each_business_sees_only_its_own_booking(
    client: TestClient, probe: TestClient, booking_ids: dict[str, int]
) -> None:
    _log_in_as(client, probe, "owner-b")

    assert probe.get(f"/probe/bookings/{booking_ids['b']}").status_code == 200
    assert probe.get(f"/probe/bookings/{booking_ids['a']}").status_code == 404
