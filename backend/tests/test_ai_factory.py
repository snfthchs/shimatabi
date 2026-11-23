import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai.factory import describe_provider, get_provider
from app.ai.fallback import FallbackProvider
from app.ai.mock_provider import MockProvider
from app.ai.provider import Conditions
from app.config import DEFAULT_ANTHROPIC_MODEL, Settings
from app.deps import get_concierge_provider
from app.main import app
from app.models import Category


def _settings(api_key: str | None = None, model: str = DEFAULT_ANTHROPIC_MODEL) -> Settings:
    return Settings(
        app_env="development",
        pii_encryption_key=None,
        anthropic_api_key=api_key,
        anthropic_model=model,
    )


def test_mock_provider_is_selected_without_an_api_key() -> None:
    assert isinstance(get_provider(_settings()), MockProvider)


def test_llm_provider_with_a_mock_fallback_is_selected_with_an_api_key() -> None:
    provider = get_provider(_settings("sk-ant-dummy-for-test"))

    assert isinstance(provider, FallbackProvider)


def test_the_same_provider_is_reused_for_the_same_settings() -> None:
    # 通信の準備と、失敗の記録（待機の時間）を、リクエストをまたいで持つため
    first = get_provider(_settings("sk-ant-dummy-for-test", "claude-haiku-5-5"))
    second = get_provider(_settings("sk-ant-dummy-for-test", "claude-haiku-5-5"))
    other_model = get_provider(_settings("sk-ant-dummy-for-test", "claude-sonnet-5-5"))

    assert first is second
    assert first is not other_model


def test_the_provider_follows_the_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_concierge_provider(), MockProvider)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")  # `.env.example` をコピーして、空のままの場合
    assert isinstance(get_concierge_provider(), MockProvider)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy-for-test")
    assert isinstance(get_concierge_provider(), FallbackProvider)


def test_describe_provider_never_includes_the_api_key() -> None:
    assert "モック" in describe_provider(_settings())

    text = describe_provider(_settings("sk-ant-secret-value", "claude-sonnet-5-5"))

    assert "claude-sonnet-5-5" in text
    assert "sk-ant-secret-value" not in text


def test_startup_succeeds_without_an_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    from app.db import create_db_engine

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
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


def test_the_llm_client_does_not_make_a_traveler_wait_long() -> None:
    from app.ai.factory import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, _build_llm_provider

    provider = _build_llm_provider("sk-ant-dummy-for-test", "claude-haiku-5-5")
    client = provider._client

    assert LLM_MAX_RETRIES == 0
    assert client.max_retries == 0
    assert client.timeout == LLM_TIMEOUT_SECONDS == 15.0
