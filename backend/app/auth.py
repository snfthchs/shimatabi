"""事業者のログインセッション（ADR 0003）。

- セッションIDは、暗号論的な乱数で作る。
- DBには、セッションIDそのものではなく、SHA-256のハッシュだけを保存する（DBが漏れても、
  セッションを乗っ取られないため）。
- 有効期限は固定（8時間）。操作のたびに延長はしない。
- 期限切れのセッションは、使われたときに削除する（定期的な掃除は、本格開発の設計）。
- 同じアカウントで、複数の端末から同時にログインできる（古いセッションは消さない）。
"""

import datetime
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BusinessUser, LoginSession
from app.passwords import verify_password, verify_password_against_dummy

# ブラウザに渡すCookieの名前
SESSION_COOKIE_NAME = "shimatabi_session"

# セッションの有効期間
SESSION_TTL = datetime.timedelta(hours=8)


def generate_token() -> str:
    """セッションIDを作る（暗号論的な乱数。256ビット）。"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """セッションIDを、DBに保存する形（SHA-256の16進数。64文字）にする。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate(session: Session, login_id: str, password: str) -> BusinessUser | None:
    """ログインIDとパスワードを確かめる。正しければ事業者アカウントを、違えば None を返す。

    IDが存在しないときも、ダミーの照合を行う。応答時間の差で、IDが存在するかどうかを
    推測されにくくするため。
    """
    user = session.scalar(select(BusinessUser).where(BusinessUser.login_id == login_id))
    if user is None:
        verify_password_against_dummy(password)
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


def create_login_session(session: Session, user: BusinessUser, now: datetime.datetime) -> str:
    """ログインセッションを作って保存し、ブラウザに渡すセッションIDを返す。"""
    token = generate_token()
    session.add(
        LoginSession(
            token_hash=hash_token(token),
            business_user_id=user.id,
            created_at=now,
            expires_at=now + SESSION_TTL,
        )
    )
    session.commit()
    return token


def find_valid_session(session: Session, token: str, now: datetime.datetime) -> LoginSession | None:
    """セッションIDに対応する、有効なセッションを返す。なければ（期限切れを含む） None。"""
    login_session = session.get(LoginSession, hash_token(token))
    if login_session is None:
        return None
    if login_session.expires_at <= now:
        session.delete(login_session)
        session.commit()
        return None
    return login_session


def delete_session(session: Session, token: str) -> None:
    """セッションを削除する（ログアウト）。存在しなくても、エラーにしない。"""
    login_session = session.get(LoginSession, hash_token(token))
    if login_session is not None:
        session.delete(login_session)
        session.commit()
