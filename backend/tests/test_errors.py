from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import AppError, ErrorCode, error_body, install_error_handlers


def test_unknown_url_returns_unified_404(client: TestClient) -> None:
    response = client.get("/api/no-such-path")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "見つかりません。"}}


def test_wrong_method_returns_unified_error_and_keeps_allow_header(client: TestClient) -> None:
    response = client.get("/api/admin/login")  # ログインは POST だけ

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "HTTP_ERROR"
    assert "POST" in response.headers["allow"]


def test_app_error_is_converted_to_unified_shape() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise AppError(ErrorCode.SLOT_UNAVAILABLE, "この便は満席です。", 409)

    response = TestClient(app).get("/boom")

    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "SLOT_UNAVAILABLE", "message": "この便は満席です。"}
    }


def test_error_body_includes_details_only_when_given() -> None:
    assert "details" not in error_body(ErrorCode.NOT_FOUND, "見つかりません。")["error"]

    body = error_body(
        ErrorCode.VALIDATION_ERROR,
        "入力内容が正しくありません。",
        [{"field": "a", "type": "missing"}],
    )

    assert body["error"]["details"] == [{"field": "a", "type": "missing"}]


def test_an_unexpected_exception_returns_the_unified_500_without_its_details() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/crash")
    def crash() -> None:
        raise RuntimeError("secret-detail 090-1234-5678")

    response = TestClient(app, raise_server_exceptions=False).get("/crash")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "サーバーでエラーが発生しました。しばらくしてから、もう一度お試しください。",
        }
    }
    assert "secret-detail" not in response.text
    assert "090-1234-5678" not in response.text
