"""パスワードのハッシュ化と照合（ADR 0003）。"""

from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# argon2id。パラメータは、argon2-cffi の既定（推奨値）を使う。
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """パスワードを、argon2idでハッシュ化する。同じ入力でも、毎回違う値になる。"""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """パスワードが、ハッシュと一致するかを確かめる。壊れたハッシュは、不一致として扱う。"""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return hash_password("dummy-password-used-only-to-equalize-timing")


def verify_password_against_dummy(password: str) -> None:
    """ダミーのハッシュと照合する（結果は使わない）。

    ログインIDが存在しないときにも、存在するときと同じ程度の時間をかけるために使う。
    """
    verify_password(_dummy_hash(), password)
