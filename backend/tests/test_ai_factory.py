import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai.factory import get_provider
from app.ai.mock_provider import MockProvider
from app.ai.provider import Conditions
from app.crypto import ConfigurationError
from app.deps import get_concierge_provider
from app.main import app
from app.models import Category


def test_mock_provider_is_selected() -> None:
    assert isinstance(get_provider("mock"), MockProvider)


def test_default_is_mock_when_the_env_var_is_not_set_or_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    assert isinstance(get_concierge_provider(), MockProvider)

    monkeypatch.setenv("AI_PROVIDER", "")  # `.env.example` をコピーして、空のままの場合
    assert isinstance(get_concierge_provider(), MockProvider)


def test_llm_provider_is_not_implemented_yet() -> None:
    with pytest.raises(ConfigurationError, match="llm"):
        get_provider("llm")


def test_unknown_provider_is_an_error_without_echoing_the_value() -> None:
    with pytest.raises(ConfigurationError) as error:
        get_provider("my-secret-value")

    assert "my-secret-value" not in str(error.value)


@pytest.mark.parametrize("value", ["llm", "unknown"])
def test_startup_fails_with_a_clear_error_for_an_unusable_provider(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("AI_PROVIDER", value)

    # 起動のときに、DBを作る前に、エラーになる
    with pytest.raises(ConfigurationError, match="AI_PROVIDER"), TestClient(app):
        pass


def test_startup_succeeds_with_the_mock_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    from app.db import create_db_engine

    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setattr(
        "app.main.create_db_engine", lambda: create_db_engine(f"sqlite:///{tmp_path}/ai.db")
    )

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200


# ---- 条件の検証（LLMが出した条件も、ここを通して検証する） ----


@pytest.mark.parametrize(
    "values",
    [
        {"party_size": 0},
        {"party_size": 51},
        {"max_minutes_from_naha": -1},
        {"category": "unknown"},
        {"date": "not-a-date"},
    ],
)
def test_conditions_reject_invalid_values(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Conditions.model_validate(values)


def test_conditions_accept_a_json_like_dict() -> None:
    conditions = Conditions.model_validate(
        {"date": "2026-11-24", "time_from": "12:00:00", "kids_ok": True, "category": "marine"}
    )

    assert conditions.date == datetime.date(2026, 11, 24)
    assert conditions.time_from == datetime.time(12)
    assert conditions.category == Category.MARINE
    assert not conditions.is_empty()


def test_empty_conditions() -> None:
    assert Conditions().is_empty()
    assert not Conditions(kids_ok=True).is_empty()
