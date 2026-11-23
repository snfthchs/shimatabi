"""個人情報の暗号化（ADR 0004）。

予約者の氏名・電話番号・メールアドレスは、Fernet（認証つきの暗号化）で暗号化して保存する。
ORMの列の型（`EncryptedString`）として使うので、ほかのコードは暗号化を意識しなくてよい。

鍵は環境変数 `PII_ENCRYPTION_KEY` で渡す。カンマ区切りで複数の鍵を渡せる。
先頭の鍵で暗号化し、すべての鍵で復号を試す（鍵のローテーションの拡張点）。
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import Text
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from app.config import get_settings


class ConfigurationError(RuntimeError):
    """設定（環境変数）が足りない、または正しくないときのエラー。"""


class DecryptionError(RuntimeError):
    """保存された個人情報を復号できないときのエラー。

    メッセージには、鍵も暗号文も平文も含めない（ログに個人情報を出さないため）。
    """


_KEY_HELP = (
    "鍵は、次のコマンドで作り、`.env` の `PII_ENCRYPTION_KEY=` に書いてください。\n"
    '  backend/.venv/bin/python -c "from cryptography.fernet import Fernet; '
    'print(Fernet.generate_key().decode())"'
)


@lru_cache(maxsize=8)
def _build_cipher(raw_keys: str) -> MultiFernet:
    keys = [key.strip() for key in raw_keys.split(",") if key.strip()]
    if not keys:
        raise ConfigurationError(f"PII_ENCRYPTION_KEY が空です。\n{_KEY_HELP}")
    try:
        return MultiFernet([Fernet(key.encode("ascii")) for key in keys])
    except (ValueError, UnicodeEncodeError) as error:
        # 鍵の値そのものは、メッセージに含めない。
        raise ConfigurationError(
            "PII_ENCRYPTION_KEY の形式が正しくありません"
            "（Fernetの鍵は、44文字のURLセーフなbase64文字列です）。\n"
            f"{_KEY_HELP}"
        ) from error


def get_cipher() -> MultiFernet:
    """設定された鍵から、暗号化・復号の道具を作る。鍵が未設定・不正ならエラーにする。"""
    raw_keys = get_settings().pii_encryption_key
    if raw_keys is None:
        raise ConfigurationError(f"PII_ENCRYPTION_KEY が設定されていません。\n{_KEY_HELP}")
    return _build_cipher(raw_keys)


class EncryptedString(TypeDecorator[str]):
    """文字列を暗号化して保存し、読み出すときに復号する列の型。

    暗号化した列は、検索や並べ替えに使えない（暗号文は毎回変わるため）。
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return get_cipher().encrypt(value.encode("utf-8")).decode("ascii")

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        try:
            return get_cipher().decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken as error:
            raise DecryptionError(
                "個人情報を復号できません。鍵が違うか、データが壊れています。"
            ) from error
