"""シマタビ（仮）のAPIの入り口。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.crypto import get_cipher
from app.db import create_db_engine, init_db, make_session_factory
from app.errors import install_error_handlers
from app.routers import admin_auth, admin_bookings, bookings, experiences


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """起動時と終了時の処理。"""
    # 暗号化の鍵が未設定・不正なら、起動の時点で、原因の分かるエラーにする。
    get_cipher()
    engine = create_db_engine()
    init_db(engine)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    try:
        yield
    finally:
        engine.dispose()


# APIの文書も `/api` の下に置く。開発では、フロントエンドの開発サーバーが
# `/api` をこのAPIへ転送するので、同じオリジンのまま文書やOpenAPIを開ける。
app = FastAPI(
    title="シマタビ API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

install_error_handlers(app)
app.include_router(admin_auth.router)
app.include_router(admin_bookings.router)
app.include_router(experiences.router)
app.include_router(bookings.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    """疎通の確認用。画面とAPIがつながっているかを確かめる。"""
    return {"status": "ok"}
