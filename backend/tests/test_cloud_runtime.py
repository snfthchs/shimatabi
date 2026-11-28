"""クラウドで動かすための設定（PostgreSQLの接続、Cookie、シードのパスワード）。

AWSには接続しない。
"""

import dataclasses
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app import db
from app.auth import SESSION_COOKIE_NAME
from app.clock import utc_now
from app.config import Settings, get_settings
from app.db import DatabaseConfigurationError, create_db_engine
from app.models import BusinessUser
from app.passwords import verify_password
from app.seed import DEMO_PASSWORD, SeedError, run_seed

POSTGRES = Settings(
    app_env="cloud-demo",
    pii_encryption_key=None,
    db_host="db.example.internal",
    db_name="shimatabi",
    db_user="shimatabi_app",
    db_ssl_root_cert="/app/rds-ca.pem",
    aws_region="ap-northeast-1",
)


class _StopConnect(Exception):
    """実際には接続せず、接続に渡す値だけを調べるための例外。"""


def _connect_params(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_connect(*cargs: Any, **cparams: Any) -> Any:
        captured.update(cparams)
        raise _StopConnect

    monkeypatch.setattr(engine.dialect.loaded_dbapi, "connect", fake_connect)
    with pytest.raises(_StopConnect):
        engine.raw_connection()
    return captured


def test_sqlite_is_used_without_db_host(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", tmp_path / "local.db")
    assert create_db_engine().dialect.name == "sqlite"


def test_environment_variables_select_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {"DB_HOST": "db.example.internal", "DB_NAME": "n", "DB_USER": "u"}
    for name, value in {**values, "AWS_REGION": "ap-northeast-1"}.items():
        monkeypatch.setenv(name, value)
    settings = get_settings()
    assert (settings.db_auth, settings.db_sslmode, settings.db_port) == ("iam", "verify-full", 5432)
    assert create_db_engine().dialect.name == "postgresql"


def test_iam_auth_uses_a_new_token_and_verifies_the_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int, str, str]] = []

    def fake_token(host: str, port: int, user: str, region: str) -> str:
        calls.append((host, port, user, region))
        return f"token-{len(calls)}"

    monkeypatch.setattr(db, "generate_iam_auth_token", fake_token)
    engine = create_db_engine(settings=POSTGRES)

    first = _connect_params(engine, monkeypatch)
    second = _connect_params(engine, monkeypatch)

    assert (first["password"], second["password"]) == ("token-1", "token-2")
    assert first["sslmode"] == "verify-full"
    assert first["sslrootcert"] == "/app/rds-ca.pem"
    assert calls[0] == ("db.example.internal", 5432, "shimatabi_app", "ap-northeast-1")
    assert "token" not in str(engine.url)


def test_password_auth_does_not_create_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_token(*args: Any) -> str:
        raise AssertionError("トークンを作ってはいけない")

    monkeypatch.setattr(db, "generate_iam_auth_token", unexpected_token)
    settings = dataclasses.replace(POSTGRES, db_auth="password", db_password="p@ss:/word")
    engine = create_db_engine(settings=settings)

    assert _connect_params(engine, monkeypatch)["password"] == "p@ss:/word"
    assert "p@ss" not in str(engine.url)
    assert "p@ss" not in repr(settings)


@pytest.mark.parametrize(
    "changes",
    [
        {"db_name": None},
        {"db_user": None},
        {"db_auth": "trust"},
        {"db_auth": "password", "db_password": None},
        {"aws_region": None},
    ],
)
def test_incomplete_postgres_settings_are_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(DatabaseConfigurationError):
        create_db_engine(settings=dataclasses.replace(POSTGRES, **changes))


@pytest.mark.parametrize("password", [None, DEMO_PASSWORD])
def test_cloud_demo_seed_requires_a_private_password(engine: Engine, password: str | None) -> None:
    settings = Settings(app_env="cloud-demo", pii_encryption_key=None, demo_password=password)
    with pytest.raises(SeedError):
        run_seed(engine, settings=settings, reset=False, now=utc_now())


def test_seed_uses_the_given_password(engine: Engine, session: Session) -> None:
    settings = Settings(
        app_env="cloud-demo", pii_encryption_key=None, demo_password="another-example-password"
    )
    run_seed(engine, settings=settings, reset=False, now=utc_now())

    user = session.scalars(select(BusinessUser)).first()
    assert user is not None
    assert verify_password(user.password_hash, "another-example-password")
    assert not verify_password(user.password_hash, DEMO_PASSWORD)


@pytest.mark.parametrize(("setting", "expected"), [("true", True), ("", False)])
def test_cookie_secure_setting(
    client: TestClient,
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    setting: str,
    expected: bool,
) -> None:
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    monkeypatch.setenv("COOKIE_SECURE", setting)
    run_seed(engine, settings=get_settings(), reset=False, now=utc_now())
    with make_session(engine) as session:
        user = session.scalars(select(BusinessUser)).first()
        assert user is not None
        login_id = user.login_id

    response = client.post(
        "/api/admin/login", json={"login_id": login_id, "password": DEMO_PASSWORD}
    )

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE_NAME}=")
    assert ("secure" in cookie.lower()) is expected


def make_session(engine: Engine) -> Session:
    return db.make_session_factory(engine)()
