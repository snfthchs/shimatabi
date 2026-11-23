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
| lint・format・型チェック | バックエンドは `ruff`・`mypy`、フロントエンドは `eslint`・`prettier`・`tsc` |
| テスト | バックエンドは `pytest`。フロントエンドの自動テストは作らない（`docs/product/test-and-deliverables-plan.md`） |

設計判断は `docs/adr/` にある（技術スタックとDB、ログイン方式、個人情報の暗号化）。

## コマンド
<!-- AIが検証に使うコマンド。決まったら必ず書く -->
コマンドは、リポジトリ直下で実行する。

| 用途 | コマンド |
|---|---|
| 依存関係のインストール | `python3 -m venv backend/.venv` と `backend/.venv/bin/pip install -r backend/requirements-dev.txt`、`npm --prefix frontend install` |
| テスト | `cd backend && .venv/bin/pytest` |
| lint・format-check | `cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .`、`npm --prefix frontend run lint && npm --prefix frontend run format:check` |
| 型チェック | `cd backend && .venv/bin/mypy`、`npm --prefix frontend run typecheck` |
| 整形（フロントエンド） | `npm --prefix frontend run format`（Prettier。`src/api/schema.d.ts` などの生成物は対象外） |
| ビルド（フロントエンド） | `npm --prefix frontend run build` |
| ローカル起動（バックエンド） | `cd backend && .venv/bin/uvicorn app.main:app --reload --env-file ../.env`（http://localhost:8000） |
| ローカル起動（フロントエンド） | `npm --prefix frontend run dev`（http://localhost:5173。`/api` はバックエンドへ転送される） |
| デモ用データの投入 | `cd backend && .venv/bin/python -m app.seed --reset`（`APP_ENV=production` では実行できない） |

バックエンドの起動には、`.env` の `PII_ENCRYPTION_KEY`（個人情報の暗号化の鍵）が必要である。作り方は `README.md` にある。AIは `.env` を読み書きできないので、確認のときは、使い捨ての鍵を環境変数で渡す。

## ディレクトリ構成
| 場所 | 役割 |
|---|---|
| `backend/app/` | FastAPIのアプリ。`main.py` が入り口、`config.py` が環境変数の設定、`db.py` がDB接続と日時の型、`models.py` がデータモデル、`crypto.py` が個人情報の暗号化、`passwords.py` がパスワードのハッシュ化、`seed.py` がデモ用データ、`errors.py` が統一したエラー、`deps.py` が共通の依存（DBセッション・現在時刻・ログイン中の事業者）、`auth.py` がログインセッション、`scoping.py` が自社のデータに絞る条件、`routers/` が各APIのルーター、`services/` が予約・体験検索の処理、`schemas.py` がAPIの入出力、`masking.py` が個人情報のマスク、`contact.py` が連絡先の正規化と照合、`ai/` がAIコンシェルジュのプロバイダー（約束事、ルールベースのモック、LLM（Claude）、失敗時にモックへ切り替える部品、`ANTHROPIC_API_KEY` の有無で選ぶ部品、AIに渡す前の個人情報のガード） |
| `backend/tests/` | バックエンドのテスト |
| `backend/scripts/` | 補助スクリプト（`dump_openapi.py` は、OpenAPIの定義をJSONで出力する。起動も鍵も不要） |
| `frontend/src/` | Reactのアプリ。`main.tsx` が入り口（`QueryClient` と `BrowserRouter`）、`App.tsx` がルート、`pages/` が画面（旅行者向けと、事業者向けの `Admin*`）、`components/` が部品、`api/` がAPI呼び出し（`client.ts` が `fetch` の包み、`hooks.ts` と `adminHooks.ts`（事業者向け）がTanStack Queryのフック、`types.ts` が型の別名、`schema.d.ts` と `openapi.json` が生成物）、`lib/` が日時・金額の整形と入力検証 |
| `docs/product/` | プロダクトの方針・設計（MVPスコープ、非機能・インフラ、設計の概要、テスト計画） |
| `docs/adr/` | 設計判断の記録 |

## このリポジトリ固有のルール
設計文書で決めた、実装時に守ること。理由は、それぞれの文書にある。

- **DBはORMだけで扱い、生SQLを書かない。** 定員の更新は、行ロックに頼らず、条件付きUPDATEで行う。日時はUTC・タイムゾーン付きで扱う（`docs/adr/0002-tech-stack-and-database.md`）。
- **便の `booked_count`（予約済み人数）は、`app/services/bookings.py` の条件付きUPDATEだけで書き換える。** ほかの場所で、読んでから書き込まない（同時に来た予約で、定員を超えたり、人数が食い違ったりするため）。予約の作成・承認・却下は、その関数を使う。例外は、デモ用のシード（`app/seed.py`）だけで、予約の人数から計算した値を、最初に入れる。
- **個人情報（予約者の氏名・電話・メール）は、暗号化して保存する。** マスクはサーバー側で行い、ログ・URL・AIへの入力に出さない（`docs/adr/0004-pii-encryption-and-masking.md`）。
- **事業者向けのAPIは、ログイン中の事業者のデータだけを対象にする。** 他の事業者のデータは、存在しないもの（404）として扱う（`docs/adr/0003-authentication-session.md`）。ログイン中の事業者は `app/deps.py` の `CurrentUserDep` で取り出し、データは `app/scoping.py` の関数で絞る。
- **エラーは、統一した形で返す**（`docs/product/design-overview.md` の4.4節）。`app/errors.py` の `AppError`（`UnauthenticatedError`、`NotFoundError` など）を使う。入力された値は、個人情報を含みうるので、エラーに含めない。
- **AIには、検索も予約も任せない。** AIプロバイダー（モック／LLM）は差し替えられる構造にする（`app/ai/provider.py` の約束事）。AIが担当するのは、条件の抽出と返答文（冒頭の1文）の生成だけ。検索は `app/services/experience_search.py`、流れは `app/services/concierge.py` で行い、提案の理由は、DBの事実からアプリが作る。AIが出した条件は、`Conditions` で検証してから使う。旅行者の文章は、ログに残さず、応答にも含めない。
- **AIに渡すものは、最小にする（`docs/adr/0007-llm-provider.md`）。** LLMに渡すのは、旅行者の文章（個人情報を伏せたあと）と今日の日付、読み取った条件と見つかった件数だけ。体験の内容（DB）と、予約者の個人情報は、渡さない。旅行者の文章は、`app/ai/pii_guard.py` の `mask_personal_info` を通してから、AIに渡す（`run_concierge` の中で行うので、新しいプロバイダーを足しても、通る）。`tests/test_concierge_pii.py` が、これを守らせている。
- **LLMが失敗しても、AI相談は止めない。** `ANTHROPIC_API_KEY` がなければモック、あれば `FallbackProvider` が、失敗のときにモックへ切り替える。APIキーは、`Settings` の `repr` にも、ログにも、エラーにも出さない。
- **フロントエンドのAPIの型は、生成物を使い、手で編集しない。** `frontend/src/api/schema.d.ts` と `openapi.json` は、バックエンドのOpenAPIから `npm --prefix frontend run gen:api` で生成する。APIの入出力を変えたら、生成し直してコミットする。型は `api/types.ts` の別名を使う。
- **事業者の画面（`/admin`）の連絡先（平文）は、TanStack Queryのキャッシュに入れない。** 「連絡先を表示」は、`useQuery` ではなく `useMutation`（`api/adminHooks.ts` の `useRevealContact`）で取得し、結果は、その行の部品の状態にだけ持つ。ログアウトのときは、`['admin']` のキャッシュを捨てる。
- **フロントエンドは、個人情報（氏名・電話・メール）を、URL・`localStorage`・`sessionStorage` に残さない。** 予約の完了画面へは、ルーターの `state` だけで渡す。日時は、UTCで受け取り、画面で日本時間に直す（`lib/format.ts`）。体験の写真は、仮の自作イラストで、`frontend/public/photos/` にある。
- **フロントエンドのテーマカラー（水色）は、`frontend/src/index.css` の `brand-50〜950` で定義し、画面のコードは `brand-` の名前で参照する。** 色を変えるときは、`index.css` の1か所を直す。ボタンは、`bg-brand-500` に白い文字で、ホバーは `bg-brand-600`、無効のときは `bg-slate-300` に `text-slate-500` にする（理由と、読みやすさの注意は、`docs/adr/0006-theme-color.md`）。
- **秘密情報（鍵、APIキー）は `.env` に置き、コミットしない。** シードのデータは架空にし、本番環境（`APP_ENV=production`）では実行しない。
- **P0の機能（定員、認可、個人情報、予約の流れ）は、時間が足りなくても縮小しない**（`docs/product/mvp-scope.md`）。

## 参照ドキュメント
- `docs/product/` — 何を作るか（プロダクトの方針・仕様）
- `docs/adr/` — 設計判断の記録
- `docs/architecture.md` — 実装の詳細（API、画面の補足、AIの仕組み、セットアップの補足）
- `docs/summary.md` — 提出用の設計の要約（図つき）
- `docs/demo-checklist.md` — デモのチェックリストと、通した結果
- `docs/ai-dev-log.md` — AIとの開発の振り返り
