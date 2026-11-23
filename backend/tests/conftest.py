from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db import create_db_engine, init_db, make_session_factory


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
