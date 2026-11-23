# AGENTS.md

このリポジトリでAIエージェントが作業するための情報。
共通の開発ルール（ワークフロー、Git、公開前提の書き方）は ai-config で管理していて、ここにはこのリポジトリ固有のことだけを書く。

## 概要
「シマタビ（仮）」は、沖縄の小規模な体験事業者と旅行者をつなぐ、体験予約プラットフォームのMVPである。旅行者がスマホで体験を探して予約し、事業者が管理画面で承認する。探す入口として、AIコンシェルジュ（まずはモック）を持つ。設計と実装を合わせて4〜6時間で作る前提で、何を作り何を見送るかは `docs/product/mvp-scope.md` にある。

## 技術スタック
| 領域 | 採用 |
|---|---|
| フロントエンド | React、TypeScript、Vite、Tailwind CSS（`frontend/`） |
| バックエンド | Python 3.12、FastAPI（`backend/`） |
| データベース | SQLite（SQLAlchemy 2.x のORM経由。ファイルは `backend/data/shimatabi.db`） |
| 暗号化・ハッシュ | 個人情報は Fernet（`cryptography`）、パスワードは argon2id（`argon2-cffi`） |
| Pythonのパッケージ管理 | `pip` と `venv`（`uv` が未導入で、新しく入れる手間を避けるため） |
| フロントのパッケージ管理 | `npm`（`pnpm` が未導入のため） |
| lint・型チェック | バックエンドは `ruff`・`mypy`、フロントエンドは `eslint`・`tsc` |
| テスト | バックエンドは `pytest`。フロントエンドの自動テストは作らない（`docs/product/test-and-deliverables-plan.md`） |

設計判断は `docs/adr/` にある（技術スタックとDB、ログイン方式、個人情報の暗号化）。

## コマンド
<!-- AIが検証に使うコマンド。決まったら必ず書く -->
コマンドは、リポジトリ直下で実行する。

| 用途 | コマンド |
|---|---|
| 依存関係のインストール | `python3 -m venv backend/.venv` と `backend/.venv/bin/pip install -r backend/requirements-dev.txt`、`npm --prefix frontend install` |
| テスト | `cd backend && .venv/bin/pytest` |
| lint | `cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .`、`npm --prefix frontend run lint` |
| 型チェック | `cd backend && .venv/bin/mypy`、`npm --prefix frontend run typecheck` |
| ビルド（フロントエンド） | `npm --prefix frontend run build` |
| ローカル起動（バックエンド） | `cd backend && .venv/bin/uvicorn app.main:app --reload --env-file ../.env`（http://localhost:8000） |
| ローカル起動（フロントエンド） | `npm --prefix frontend run dev`（http://localhost:5173。`/api` はバックエンドへ転送される） |
| デモ用データの投入 | `cd backend && .venv/bin/python -m app.seed --reset`（`APP_ENV=production` では実行できない） |

バックエンドの起動には、`.env` の `PII_ENCRYPTION_KEY`（個人情報の暗号化の鍵）が必要である。作り方は `README.md` にある。AIは `.env` を読み書きできないので、確認のときは、使い捨ての鍵を環境変数で渡す。

## ディレクトリ構成
| 場所 | 役割 |
|---|---|
| `backend/app/` | FastAPIのアプリ。`main.py` が入り口、`config.py` が環境変数の設定、`db.py` がDB接続と日時の型、`models.py` がデータモデル、`crypto.py` が個人情報の暗号化、`passwords.py` がパスワードのハッシュ化、`seed.py` がデモ用データ |
| `backend/tests/` | バックエンドのテスト |
| `frontend/src/` | Reactのアプリ |
| `docs/product/` | プロダクトの方針・設計（MVPスコープ、非機能・インフラ、設計の概要、テスト計画） |
| `docs/adr/` | 設計判断の記録 |

## このリポジトリ固有のルール
設計文書で決めた、実装時に守ること。理由は、それぞれの文書にある。

- **DBはORMだけで扱い、生SQLを書かない。** 定員の更新は、行ロックに頼らず、条件付きUPDATEで行う。日時はUTC・タイムゾーン付きで扱う（`docs/adr/0002-tech-stack-and-database.md`）。
- **個人情報（予約者の氏名・電話・メール）は、暗号化して保存する。** マスクはサーバー側で行い、ログ・URL・AIへの入力に出さない（`docs/adr/0004-pii-encryption-and-masking.md`）。
- **事業者向けのAPIは、ログイン中の事業者のデータだけを対象にする。** 他の事業者のデータは、存在しないもの（404）として扱う（`docs/adr/0003-authentication-session.md`）。
- **エラーは、統一した形で返す**（`docs/product/design-overview.md` の4.4節）。
- **AIには、検索も予約も任せない。** AIプロバイダー（モック／LLM）は差し替えられる構造にする。
- **秘密情報（鍵、APIキー）は `.env` に置き、コミットしない。** シードのデータは架空にし、本番環境（`APP_ENV=production`）では実行しない。
- **P0の機能（定員、認可、個人情報、予約の流れ）は、時間が足りなくても縮小しない**（`docs/product/mvp-scope.md`）。

## 参照ドキュメント
- `docs/product/` — 何を作るか（プロダクトの方針・仕様）
- `docs/adr/` — 設計判断の記録
- `docs/ai-dev-log.md` — AIとの開発の振り返り
