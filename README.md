# シマタビ（仮）

沖縄の小規模な体験事業者と旅行者をつなぐ、体験予約プラットフォームのMVPである。旅行者がスマホで体験を探して予約し、事業者が管理画面で承認する。探す入口として、AIコンシェルジュ（まずはモック）を持つ。

何を作り、何を見送ったかは、[MVPスコープ](docs/product/mvp-scope.md)にある。設計の全体は `docs/product/` と `docs/adr/` にまとめている。

> 現在は、体験・予約のAPI（Issue D）まで。AIコンシェルジュと画面は、Issue E 以降で追加する。

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

予約者の個人情報（氏名・電話・メール）を暗号化する鍵が必要である。次のコマンドで鍵を作り、出力された文字列を、`.env` の `PII_ENCRYPTION_KEY=` のあとに書く。

```bash
backend/.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

- 鍵がないと、バックエンドは起動しない（起動のときに、原因が分かるエラーになる）。
- 鍵は、コミットしない。鍵をなくすと、暗号化した個人情報は読めなくなる（デモ用のDBは、シードで作り直せる）。
- 鍵は、カンマ区切りで複数書ける。先頭の鍵で暗号化し、すべての鍵で復号を試す（鍵を入れ替えるときに使う）。

## デモ用データの投入（シード）
架空の事業者・体験・便・予約を、DBに入れる。`backend/` で実行する。

```bash
cd backend && .venv/bin/python -m app.seed --reset
```

- `--reset` は、すべてのテーブルを消して作り直してから投入する。`--reset` なしは、空のDBにだけ投入する。
- **デモの直前に `--reset` で作り直す**と、今日の午後の便が受付中の状態になる。今日の便は、実行した時刻より後のものだけを作る。
- 事業者アカウントのログインIDは、`demo-marine`、`demo-craft`、`demo-night`、`demo-food`。パスワードは、架空・デモ専用の固定値で、`backend/app/seed.py` の `DEMO_PASSWORD` にある。
- `.env` の `APP_ENV=production` のときは、シードを実行できない。
- DBのファイルは `backend/data/shimatabi.db` にできる（コミットされない）。

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

## 事業者のログイン（API）
| メソッド | パス | 内容 |
|---|---|---|
| POST | `/api/admin/login` | ログインIDとパスワードでログインする。セッションのCookieが設定される |
| POST | `/api/admin/logout` | ログアウトする（サーバー側のセッションを削除し、Cookieを消す） |
| GET | `/api/admin/me` | ログイン中の事業者の情報を返す |

- セッションの有効期限は8時間（固定）。Cookie は `HttpOnly`、`SameSite=Lax`（HTTPSのときは `Secure`）。
- デモ用のアカウントは、シードを投入すると使える（ログインIDとパスワードは、上のシードの節にある）。
- エラーは、すべて `{"error": {"code": "...", "message": "..."}}` の形で返る。

## 体験・予約のAPI
旅行者向け（ログイン不要）:

| メソッド | パス | 内容 |
|---|---|---|
| GET | `/api/experiences` | 体験の一覧。クエリ: `date`（日本時間の日付）、`party_size`、`kids_ok`、`rain_ok`、`area`、`category`、`max_minutes_from_naha`。条件に合う受付中の便を持つ体験だけを返す |
| GET | `/api/experiences/{id}` | 体験の詳細と、これから始まる受付中の便（満席は残席0で含む） |
| POST | `/api/bookings` | 予約を作る（201）。氏名・電話・メールは、すべて必須。即時確定の体験は確定、承認制の体験は承認待ちになる |
| POST | `/api/bookings/lookup` | 予約番号と連絡先（電話またはメール）で、予約の状態を確認する。連絡先は個人情報なので、URLではなくPOSTの本文で送る |

事業者向け（要ログイン。自社のデータだけ。他社のデータは404）:

| メソッド | パス | 内容 |
|---|---|---|
| GET | `/api/admin/slots` | 自社の便と、便ごとの予約の状況（承認待ち・確定の人数） |
| GET | `/api/admin/bookings` | 自社の予約の一覧。氏名・電話・メールは、サーバー側でマスクして返す |
| POST | `/api/admin/bookings/{id}/approve` | 承認待ちの予約を承認する |
| POST | `/api/admin/bookings/{id}/reject` | 承認待ちの予約を却下し、押さえていた定員を解放する |
| GET | `/api/admin/bookings/{id}/contact` | 1件の予約の連絡先を、平文で返す（「連絡先を表示」） |

- **定員は、条件付きUPDATEで守る**。承認待ちの予約も、定員に数える。満席・開始後・中止の便への予約は、409（`SLOT_UNAVAILABLE`）。すでに処理した予約の承認・却下は、409（`INVALID_STATE`）。
- 日時のレスポンスは、UTC（`Z` つき）。画面が、日本時間に直して表示する。

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
