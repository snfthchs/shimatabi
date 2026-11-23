"""パスワードのハッシュ化（ADR 0003）。

ここにあるのは、ハッシュ化だけである。照合とログインの処理は、Issue C で追加する。
"""

from argon2 import PasswordHasher

# argon2id。パラメータは、argon2-cffi の既定（推奨値）を使う。
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """パスワードを、argon2idでハッシュ化する。同じ入力でも、毎回違う値になる。"""
    return _hasher.hash(password)
