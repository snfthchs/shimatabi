import pytest

from app.config import DEFAULT_ANTHROPIC_MODEL, Settings, get_settings

_NAMES = ("APP_ENV", "PII_ENCRYPTION_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL")


def test_defaults_when_env_is_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _NAMES:
        monkeypatch.delenv(name, raising=False)

    settings = get_settings()

    assert settings.app_env == "development"
    assert settings.pii_encryption_key is None
    assert settings.anthropic_api_key is None
    assert settings.anthropic_model == DEFAULT_ANTHROPIC_MODEL == "claude-haiku-5-5"


def test_empty_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # `.env.example` をコピーして、値を空のままにした場合の動き
    for name in _NAMES:
        monkeypatch.setenv(name, "")

    settings = get_settings()

    assert settings.app_env == "development"
    assert settings.pii_encryption_key is None
    assert settings.anthropic_api_key is None
    assert settings.anthropic_model == DEFAULT_ANTHROPIC_MODEL


def test_values_are_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PII_ENCRYPTION_KEY", "dummy-key-for-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy-for-test")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

    settings = get_settings()

    assert settings.app_env == "production"
    assert settings.pii_encryption_key == "dummy-key-for-test"
    assert settings.anthropic_api_key == "sk-ant-dummy-for-test"
    assert settings.anthropic_model == "claude-sonnet-5-5"


def test_the_encryption_key_is_not_shown_in_repr() -> None:
    settings = Settings(app_env="development", pii_encryption_key="secret-fernet-key-value")

    assert "secret-fernet-key-value" not in repr(settings)
    assert "secret-fernet-key-value" not in str(settings)


def test_the_api_key_is_not_shown_in_repr() -> None:
    # ログやエラーに、設定を表示しても、秘密の値が出ないこと
    settings = Settings(
        app_env="development",
        pii_encryption_key=None,
        anthropic_api_key="sk-ant-secret-value",
    )

    assert "sk-ant-secret-value" not in repr(settings)
