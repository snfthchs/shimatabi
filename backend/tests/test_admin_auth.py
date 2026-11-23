import datetime
import hashlib
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, SESSION_TTL
from app.main import app
from tests.factories import create_business, create_business_user
from tests.fakes import FakeClock

LOGIN_ID = "demo-owner"
PASSWORD = "correct-horse-battery"


@pytest.fixture
def owner(session: Session) -> None:
    business = create_business(session, "潮風テスト事業者")
    create_business_user(session, business, login_id=LOGIN_ID, password=PASSWORD)
    session.commit()


def _login(client: TestClient, login_id: str = LOGIN_ID, password: str = PASSWORD) -> Any:
    # TestClient の戻り値は、型が解決されない（Starlette 1.x が httpx2 を使う設計のため）。
    return client.post("/api/admin/login", json={"login_id": login_id, "password": password})


def _session_row_count(session: Session) -> int:
    return int(session.execute(text("SELECT COUNT(*) FROM login_sessions")).scalar_one())


@pytest.mark.usefixtures("owner")
def test_login_returns_the_business_and_sets_a_safe_cookie(client: TestClient) -> None:
    response = _login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["login_id"] == LOGIN_ID
    assert body["business"]["name"] == "潮風テスト事業者"
    cookie = response.headers["set-cookie"].lower()
    assert f"{SESSION_COOKIE_NAME}=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert f"max-age={int(SESSION_TTL.total_seconds())}" in cookie
    assert "secure" not in cookie  # http のとき（ローカルの開発）は付けない
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.usefixtures("owner")
def test_cookie_is_secure_over_https(client: TestClient) -> None:
    https_client = TestClient(app, base_url="https://testserver")

    response = _login(https_client)

    assert "secure" in response.headers["set-cookie"].lower()


@pytest.mark.usefixtures("owner")
def test_me_returns_the_logged_in_business(client: TestClient) -> None:
    _login(client)

    response = client.get("/api/admin/me")

    assert response.status_code == 200
    assert response.json()["business"]["name"] == "潮風テスト事業者"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.usefixtures("owner")
def test_wrong_password_and_unknown_id_look_the_same(client: TestClient) -> None:
    wrong_password = _login(client, password="wrong-password")
    unknown_id = _login(client, login_id="no-such-user")

    assert wrong_password.status_code == unknown_id.status_code == 401
    assert wrong_password.json() == unknown_id.json()
    assert wrong_password.json()["error"]["code"] == "UNAUTHENTICATED"
    assert SESSION_COOKIE_NAME not in wrong_password.headers.get("set-cookie", "")


@pytest.mark.usefixtures("owner")
def test_only_the_hash_of_the_session_id_is_stored(client: TestClient, session: Session) -> None:
    _login(client)
    cookie_value = client.cookies.get(SESSION_COOKIE_NAME)
    assert cookie_value is not None

    stored = session.execute(text("SELECT token_hash FROM login_sessions")).scalar_one()

    assert stored == hashlib.sha256(cookie_value.encode("utf-8")).hexdigest()
    assert len(stored) == 64
    assert stored != cookie_value


@pytest.mark.usefixtures("owner")
def test_logout_invalidates_the_session(client: TestClient, session: Session) -> None:
    _login(client)
    assert _session_row_count(session) == 1

    response = client.post("/api/admin/logout")

    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()  # Cookie を消す
    assert _session_row_count(session) == 0  # サーバー側のセッションも削除される
    assert client.get("/api/admin/me").status_code == 401


@pytest.mark.usefixtures("owner")
def test_a_copied_session_id_stops_working_after_logout(client: TestClient) -> None:
    _login(client)
    token = client.cookies.get(SESSION_COOKIE_NAME)
    assert token is not None
    client.post("/api/admin/logout")

    # ブラウザのCookieが消えたあとに、控えておいたセッションIDを送り直されても、使えない。
    # サーバー側のセッションが削除されているため。
    client.cookies.set(SESSION_COOKIE_NAME, token)

    assert client.get("/api/admin/me").status_code == 401


def test_logout_without_login_is_not_an_error(client: TestClient) -> None:
    assert client.post("/api/admin/logout").status_code == 204


@pytest.mark.usefixtures("owner")
def test_expired_session_is_rejected_and_deleted(
    client: TestClient, clock: FakeClock, session: Session
) -> None:
    _login(client)

    clock.now += SESSION_TTL + datetime.timedelta(seconds=1)
    response = client.get("/api/admin/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert _session_row_count(session) == 0


@pytest.mark.usefixtures("owner")
def test_session_is_valid_just_before_expiry(client: TestClient, clock: FakeClock) -> None:
    _login(client)

    clock.now += SESSION_TTL - datetime.timedelta(seconds=1)

    assert client.get("/api/admin/me").status_code == 200


@pytest.mark.usefixtures("owner")
def test_session_is_not_extended_by_use(client: TestClient, clock: FakeClock) -> None:
    # 有効期限は固定。途中で使っても、延長されない。
    _login(client)
    clock.now += SESSION_TTL - datetime.timedelta(hours=1)
    assert client.get("/api/admin/me").status_code == 200

    clock.now += datetime.timedelta(hours=1, seconds=1)

    assert client.get("/api/admin/me").status_code == 401


def test_missing_cookie_is_401(client: TestClient) -> None:
    response = client.get("/api/admin/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_unknown_session_id_is_401(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE_NAME, "not-a-real-session-id")

    assert client.get("/api/admin/me").status_code == 401


@pytest.mark.usefixtures("owner")
def test_one_account_can_log_in_from_several_devices(client: TestClient) -> None:
    other_device = TestClient(app)  # Cookie を共有しない、別の端末

    assert _login(client).status_code == 200
    assert _login(other_device).status_code == 200
    assert client.get("/api/admin/me").status_code == 200
    assert other_device.get("/api/admin/me").status_code == 200

    client.post("/api/admin/logout")  # 片方がログアウトしても、もう片方は続く

    assert client.get("/api/admin/me").status_code == 401
    assert other_device.get("/api/admin/me").status_code == 200


def test_login_validation_error_has_unified_shape(client: TestClient) -> None:
    response = client.post("/api/admin/login", json={})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert {detail["field"] for detail in error["details"]} == {"login_id", "password"}


def test_validation_error_does_not_echo_the_input(client: TestClient) -> None:
    too_long_password = "SECRET" * 40

    response = client.post(
        "/api/admin/login", json={"login_id": "demo-owner", "password": too_long_password}
    )

    assert response.status_code == 422
    assert "SECRET" not in response.text
