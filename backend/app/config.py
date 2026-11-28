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
    # 秘密情報なので、`repr`（ログやエラーへの表示）には出さない。
    pii_encryption_key: str | None = field(repr=False)
    # AnthropicのAPIキー。設定されているときだけ、LLMでAIコンシェルジュを動かす。
    # 秘密情報なので、`repr`（ログやエラーへの表示）には出さない。
    anthropic_api_key: str | None = field(default=None, repr=False)
    # LLMのモデル。
    anthropic_model: str = DEFAULT_ANTHROPIC_MODEL
    # ログインのCookieに、必ず `Secure` を付ける（HTTPSの手前で、通信がHTTPになる構成のため）。
    cookie_secure: bool = False
    # デモ用の事業者のパスワード。未設定なら、ローカル用の公開している値を使う。
    demo_password: str | None = field(default=None, repr=False)
    # 以下は、PostgreSQLに接続する場合の設定。`db_host` が未設定なら、SQLiteを使う。
    db_host: str | None = None
    db_port: int = 5432
    db_name: str | None = None
    db_user: str | None = None
    # `iam`（IAMの短命のトークン）か、`password`。
    db_auth: str = "iam"
    db_password: str | None = field(default=None, repr=False)
    # サーバー証明書の検証の方法と、信頼する認証局の証明書のファイル。
    db_sslmode: str = "verify-full"
    db_ssl_root_cert: str | None = None
    aws_region: str | None = None


def get_settings() -> Settings:
    """環境変数から設定を作る。"""
    # `.env.example` をコピーして値が空のままでも、既定値になるよう `or` を使う。
    return Settings(
        app_env=os.environ.get("APP_ENV") or "development",
        pii_encryption_key=os.environ.get("PII_ENCRYPTION_KEY") or None,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        anthropic_model=os.environ.get("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL,
        cookie_secure=(os.environ.get("COOKIE_SECURE") or "").lower() == "true",
        demo_password=os.environ.get("DEMO_PASSWORD") or None,
        db_host=os.environ.get("DB_HOST") or None,
        db_port=int(os.environ.get("DB_PORT") or 5432),
        db_name=os.environ.get("DB_NAME") or None,
        db_user=os.environ.get("DB_USER") or None,
        db_auth=os.environ.get("DB_AUTH") or "iam",
        db_password=os.environ.get("DB_PASSWORD") or None,
        db_sslmode=os.environ.get("DB_SSLMODE") or "verify-full",
        db_ssl_root_cert=os.environ.get("DB_SSL_ROOT_CERT") or None,
        aws_region=os.environ.get("AWS_REGION") or None,
    )
