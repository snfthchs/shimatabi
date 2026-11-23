import pytest

from app.config import get_settings


def test_defaults_when_env_is_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_ENV", "AI_PROVIDER", "PII_ENCRYPTION_KEY"):
        monkeypatch.delenv(name, raising=False)

    settings = get_settings()

    assert settings.app_env == "development"
    assert settings.ai_provider == "mock"
    assert settings.pii_encryption_key is None


def test_empty_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # `.env.example` をコピーして、値を空のままにした場合の動き
    for name in ("APP_ENV", "AI_PROVIDER", "PII_ENCRYPTION_KEY"):
        monkeypatch.setenv(name, "")

    settings = get_settings()

    assert settings.app_env == "development"
    assert settings.ai_provider == "mock"
    assert settings.pii_encryption_key is None


def test_values_are_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AI_PROVIDER", "llm")
    monkeypatch.setenv("PII_ENCRYPTION_KEY", "dummy-key-for-test")

    settings = get_settings()

    assert settings.app_env == "production"
    assert settings.ai_provider == "llm"
    assert settings.pii_encryption_key == "dummy-key-for-test"
