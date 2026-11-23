"""環境変数から読み込む設定。

値は `.env`（コミットしない）か、実行環境の環境変数で渡す。
名前と、鍵の作り方は、リポジトリ直下の `.env.example` に書いてある。
"""

import os
from dataclasses import dataclass, field

# LLMのモデルの既定。もっとも安く、速いモデル。選択肢は、READMEにある。
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-5-5"


@dataclass(frozen=True)
class Settings:
    """アプリの設定。"""

    # 実行環境。`production` のときは、シードを実行できない。
    app_env: str
    # 個人情報の暗号化に使う鍵（Fernetの鍵）。未設定なら None。
    pii_encryption_key: str | None
    # AnthropicのAPIキー。設定されているときだけ、LLMでAIコンシェルジュを動かす。
    # 秘密情報なので、`repr`（ログやエラーへの表示）には出さない。
    anthropic_api_key: str | None = field(default=None, repr=False)
    # LLMのモデル。
    anthropic_model: str = DEFAULT_ANTHROPIC_MODEL


def get_settings() -> Settings:
    """環境変数から設定を作る。"""
    # `.env.example` をコピーして値が空のままでも、既定値になるよう `or` を使う。
    return Settings(
        app_env=os.environ.get("APP_ENV") or "development",
        pii_encryption_key=os.environ.get("PII_ENCRYPTION_KEY") or None,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.environ.get("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL,
    )
