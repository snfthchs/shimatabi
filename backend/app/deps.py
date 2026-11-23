"""APIの処理から使う、共通の依存（FastAPIの `Depends`）。

テストでは、`app.dependency_overrides` で、`get_session_factory` と `get_now` を差し替える。
"""

import datetime
from collections.abc import Iterator
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.ai.factory import get_provider
from app.ai.provider import ConciergeProvider
from app.auth import SESSION_COOKIE_NAME, find_valid_session
from app.clock import utc_now
from app.config import get_settings
from app.errors import UnauthenticatedError
from app.models import BusinessUser


def get_session_factory(request: Request) -> sessionmaker[Session]:
    """起動時に作ったセッションの工場を返す。"""
    factory: sessionmaker[Session] = request.app.state.session_factory
    return factory


def get_session(
    factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> Iterator[Session]:
    """リクエストごとに、DBのセッションを1つ作り、終わったら閉じる。"""
    with factory() as session:
        yield session


def get_now() -> datetime.datetime:
    """現在の日時（UTC）。テストでは、差し替えて時刻を固定する。"""
    return utc_now()


SessionDep = Annotated[Session, Depends(get_session)]
NowDep = Annotated[datetime.datetime, Depends(get_now)]


def get_current_business_user(
    session: SessionDep,
    now: NowDep,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> BusinessUser:
    """ログイン中の事業者アカウントを返す。未ログイン・期限切れ・不正なら、401にする。

    事業者向けのAPIは、これを使う。データを取り出すときは、`app.scoping` の関数で、
    ログイン中の事業者のデータだけに絞る。
    """
    if token is None:
        raise UnauthenticatedError()
    login_session = find_valid_session(session, token, now)
    if login_session is None:
        raise UnauthenticatedError()
    return login_session.business_user


CurrentUserDep = Annotated[BusinessUser, Depends(get_current_business_user)]


def get_concierge_provider() -> ConciergeProvider:
    """環境変数 `AI_PROVIDER` で選んだ、AIプロバイダー。テストでは、差し替えられる。"""
    return get_provider(get_settings().ai_provider)


ProviderDep = Annotated[ConciergeProvider, Depends(get_concierge_provider)]
