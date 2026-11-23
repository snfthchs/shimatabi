"""シマタビ（仮）のAPIの入り口。"""

from fastapi import FastAPI

# APIの文書も `/api` の下に置く。開発では、フロントエンドの開発サーバーが
# `/api` をこのAPIへ転送するので、同じオリジンのまま文書やOpenAPIを開ける。
app = FastAPI(
    title="シマタビ API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """疎通の確認用。画面とAPIがつながっているかを確かめる。"""
    return {"status": "ok"}
