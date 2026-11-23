"""環境変数から読み込む設定。

値は `.env`（コミットしない）か、実行環境の環境変数で渡す。
名前と、鍵の作り方は、リポジトリ直下の `.env.example` に書いてある。
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """アプリの設定。"""

    # 実行環境。`production` のときは、シードを実行できない。
    app_env: str
    # AIプロバイダー。`mock`（既定）または `llm`。
    ai_provider: str
    # 個人情報の暗号化に使う鍵（Fernetの鍵）。未設定なら None。
    pii_encryption_key: str | None


def get_settings() -> Settings:
    """環境変数から設定を作る。"""
    # `.env.example` をコピーして値が空のままでも、既定値になるよう `or` を使う。
    return Settings(
        app_env=os.environ.get("APP_ENV") or "development",
        ai_provider=os.environ.get("AI_PROVIDER") or "mock",
        pii_encryption_key=os.environ.get("PII_ENCRYPTION_KEY") or None,
    )
