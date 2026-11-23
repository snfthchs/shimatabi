import datetime
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db import create_db_engine, init_db, make_session_factory
from app.deps import get_now, get_session_factory
from app.main import app
from tests.fakes import FakeClock


@pytest.fixture(autouse=True)
def pii_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """テストごとに、使い捨ての暗号化の鍵を環境変数に設定する（本番の鍵は使わない）。"""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("PII_ENCRYPTION_KEY", key)
    return key


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    """テストごとに作り直す、一時ファイルのSQLite。

    同時実行のテストでも使えるよう、メモリ上ではなくファイルにする。
    """
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with make_session_factory(engine)() as session:
        yield session


@pytest.fixture
def clock() -> FakeClock:
    """固定した時計。テストの中で `clock.now` を進めると、APIが見る現在時刻も進む。"""
    return FakeClock(now=datetime.datetime(2026, 11, 24, 1, 0, tzinfo=datetime.UTC))


@pytest.fixture
def client(engine: Engine, clock: FakeClock) -> Iterator[TestClient]:
    """APIを呼ぶクライアント。DBは一時ファイル、現在時刻は固定した時計に差し替える。

    `with` を使わないので、アプリの起動処理（実際のDBファイルの作成）は動かない。
    """
    factory = make_session_factory(engine)
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_now] = lambda: clock.now
    yield TestClient(app)
    app.dependency_overrides.clear()
