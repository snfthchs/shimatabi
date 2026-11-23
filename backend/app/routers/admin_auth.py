"""事業者のログイン・ログアウト・ログイン中の事業者の情報（`/api/admin`）。"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response
from pydantic import BaseModel, Field

from app.auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL,
    authenticate,
    create_login_session,
    delete_session,
)
from app.deps import CurrentUserDep, NowDep, SessionDep
from app.errors import UnauthenticatedError
from app.models import BusinessUser

router = APIRouter(prefix="/api/admin", tags=["admin"])


class LoginRequest(BaseModel):
    login_id: str = Field(min_length=1, max_length=50)
    # 長すぎる入力で、ハッシュの計算に時間をかけさせられないよう、上限を設ける。
    password: str = Field(min_length=1, max_length=200)


class BusinessOut(BaseModel):
    id: int
    name: str
    area: str


class MeOut(BaseModel):
    login_id: str
    business: BusinessOut


def _me(user: BusinessUser) -> MeOut:
    return MeOut(
        login_id=user.login_id,
        business=BusinessOut(id=user.business.id, name=user.business.name, area=user.business.area),
    )


def _is_https(request: Request) -> bool:
    # HTTPSのときだけ、Cookieに `Secure` を付ける（ローカルの開発は http）。
    return request.url.scheme == "https"


@router.post("/login", response_model=MeOut)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    now: NowDep,
) -> MeOut:
    """ログインして、セッションのCookieを設定する。"""
    user = authenticate(session, body.login_id, body.password)
    if user is None:
        # IDが違う場合も、パスワードが違う場合も、同じメッセージにする。
        raise UnauthenticatedError("IDまたはパスワードが違います。")
    token = create_login_session(session, user, now)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=_is_https(request),
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return _me(user)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> Response:
    """サーバー側のセッションを削除して、Cookieを消す。ログインしていなくても、エラーにしない。"""
    if token is not None:
        delete_session(session, token)
    response = Response(status_code=204)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_is_https(request),
    )
    return response


@router.get("/me", response_model=MeOut)
def me(user: CurrentUserDep, response: Response) -> MeOut:
    """ログイン中の事業者の情報を返す。"""
    response.headers["Cache-Control"] = "no-store"
    return _me(user)
