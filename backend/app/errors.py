"""統一したエラーの形（`docs/product/design-overview.md` の4.4節）。

すべてのエラーを、次の形で返す。

    {"error": {"code": "SLOT_UNAVAILABLE", "message": "この便は満席、または受付を終了しています。"}}

入力エラー（422）には、どの項目が、どんな理由で正しくないかを、`details` に入れる。
入力された値そのものは、個人情報を含みうるので、エラーには入れない。
"""

import enum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode(enum.StrEnum):
    """エラーの種類。画面は、この値で表示を切り替える。"""

    VALIDATION_ERROR = "VALIDATION_ERROR"  # 入力が正しくない（422）
    UNAUTHENTICATED = "UNAUTHENTICATED"  # ログインが必要、または期限切れ（401）
    NOT_FOUND = "NOT_FOUND"  # 存在しない、または見る権限がない（404）
    SLOT_UNAVAILABLE = "SLOT_UNAVAILABLE"  # 満席、または受付を終了した便（409）
    INVALID_STATE = "INVALID_STATE"  # すでに承認・却下された予約への操作など（409）
    HTTP_ERROR = "HTTP_ERROR"  # 上記以外のHTTPエラー（405 など）


class AppError(Exception):
    """アプリで決めたエラー。例外ハンドラが、統一した形のレスポンスに変える。"""

    def __init__(self, code: ErrorCode, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class UnauthenticatedError(AppError):
    """ログインが必要、または期限切れ（401）。"""

    def __init__(self, message: str = "ログインが必要です。") -> None:
        super().__init__(ErrorCode.UNAUTHENTICATED, message, 401)


class NotFoundError(AppError):
    """存在しない、または見る権限がない（404）。他の事業者のデータも、これで返す。"""

    def __init__(self, message: str = "見つかりません。") -> None:
        super().__init__(ErrorCode.NOT_FOUND, message, 404)


def error_body(
    code: ErrorCode, message: str, details: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    """統一した形のエラーの本文を作る。"""
    error: dict[str, Any] = {"code": code.value, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def install_error_handlers(app: FastAPI) -> None:
    """アプリに、統一したエラーの形を返す例外ハンドラを登録する。"""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # 入力された値（`input`）は、個人情報を含みうるので、返さない。
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"][1:]),
                "type": str(error["type"]),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body(ErrorCode.VALIDATION_ERROR, "入力内容が正しくありません。", details),
        )

    # FastAPI の HTTPException ではなく、Starlette の方に登録する。
    # 存在しないURL（404）など、Starlette 自身が出すエラーも、同じ形にそろえるため。
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            code, message = ErrorCode.NOT_FOUND, "見つかりません。"
        elif exc.status_code == 401:
            code, message = ErrorCode.UNAUTHENTICATED, "ログインが必要です。"
        else:
            code, message = ErrorCode.HTTP_ERROR, "リクエストを処理できません。"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
            headers=getattr(exc, "headers", None),
        )
