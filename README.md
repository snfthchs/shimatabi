# シマタビ（仮）

沖縄の小規模な体験事業者と旅行者をつなぐ、体験予約プラットフォームのMVPである。旅行者がスマホで体験を探して予約し、事業者が管理画面で承認する。探す入口として、AIコンシェルジュ（まずはモック）を持つ。

何を作り、何を見送ったかは、[MVPスコープ](docs/product/mvp-scope.md)にある。設計の全体は `docs/product/` と `docs/adr/` にまとめている。

> 現在は、雛形（Issue A）の段階で、画面とAPIの疎通だけが確認できる。機能は、Issue B 以降で追加する。

## 必要なもの
- Python 3.12
- Node.js（npm つき）

## セットアップ
リポジトリ直下で、次を実行する。

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt
npm --prefix frontend install
```

設定は、`.env.example` を `.env` にコピーして使う。`.env` はコミットしない。空のままの項目は、既定値になる。

```bash
cp .env.example .env
```

## 起動
ターミナルを2つ開いて、それぞれで起動する。

バックエンド（http://localhost:8000）:

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --env-file ../.env
```

フロントエンド（http://localhost:5173）:

```bash
npm --prefix frontend run dev
```

画面（http://localhost:5173）に「APIとの接続: つながっています」と出れば、画面とAPIがつながっている。フロントエンドの開発サーバーが `/api` をバックエンドへ転送するので、画面とAPIは同じオリジンで動く。APIの文書は http://localhost:5173/api/docs で見られる。

## テスト・lint・型チェック
バックエンド:

```bash
cd backend && .venv/bin/pytest
cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
cd backend && .venv/bin/mypy
```

フロントエンド:

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

## ディレクトリ構成
| 場所 | 役割 |
|---|---|
| `backend/` | FastAPIのアプリとテスト |
| `frontend/` | Reactのアプリ |
| `docs/product/` | プロダクトの方針・設計 |
| `docs/adr/` | 設計判断の記録 |
| `docs/ai-dev-log.md` | AIとの開発の振り返り |
