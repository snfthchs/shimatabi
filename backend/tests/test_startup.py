from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect

from app.crypto import ConfigurationError
from app.db import create_db_engine
from app.main import app


def test_startup_fails_with_clear_error_when_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PII_ENCRYPTION_KEY")

    with pytest.raises(ConfigurationError, match="PII_ENCRYPTION_KEY"):
        with TestClient(app):
            pass


def test_startup_creates_tables(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 実際のDBファイル（backend/data/）を使わず、一時ファイルのDBに差し替える。
    engine_holder: list[Engine] = []

    def create_test_engine() -> Engine:
        engine = create_db_engine(f"sqlite:///{tmp_path / 'startup.db'}")
        engine_holder.append(engine)
        return engine

    monkeypatch.setattr("app.main.create_db_engine", create_test_engine)

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

    assert (
        "bookings"
        in inspect(create_db_engine(f"sqlite:///{tmp_path / 'startup.db'}")).get_table_names()
    )
    assert len(engine_holder) == 1
