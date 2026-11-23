# シマタビ（仮）

沖縄の小規模な体験事業者と旅行者をつなぐ、体験予約プラットフォームのMVPである。旅行者がスマホで体験を探して予約し、事業者が管理画面で承認する。探す入口として、AIコンシェルジュ（まずはモック）を持つ。

設計・API・実装の詳細は、[アーキテクチャと実装の詳細](docs/architecture.md)にある。何を作り、何を見送ったかは、[MVPスコープ](docs/product/mvp-scope.md)にある。

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

設定は、`.env.example` を `.env` にコピーして使う。`.env` はコミットしない。

```bash
cp .env.example .env
```

予約者の個人情報（氏名・電話・メール）を暗号化する鍵が必要である。次のコマンドで鍵を作り、出力された文字列を、`.env` の `PII_ENCRYPTION_KEY=` のあとに書く。鍵がないと、バックエンドは起動しない。

```bash
backend/.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## デモ用データの投入（シード）
架空の事業者・体験・便・予約を、DBに入れる。**デモの直前に**実行すると、今日の午後の便が受付中の状態になる。

```bash
cd backend && .venv/bin/python -m app.seed --reset
```

事業者の画面には、次のアカウントでログインできる（すべて架空・デモ専用）。

| 事業者 | ログインID | パスワード | 備考 |
|---|---|---|---|
| 島染め工房ひだまり | `demo-craft` | `demo-only-password` | デモで使う（承認制の体験。承認待ちの予約がある） |
| 潮風マリンサービス | `demo-marine` | `demo-only-password` | 他社の予約が見えないことの確認に使う |
| やんばる星空ガイド | `demo-night` | `demo-only-password` | 同上 |
| 島ごはん教室 | `demo-food` | `demo-only-password` | 同上 |

## AIコンシェルジュの設定
キーがなくても、AI相談は動く（ルールベースのモックで答える）。LLM（Claude）で答えさせるときだけ、`.env` に、次を書く。

| 環境変数 | 内容 |
|---|---|
| `ANTHROPIC_API_KEY` | AnthropicのAPIキー。書くと、LLMで答える。空なら、モックで答える。LLMが失敗したとき（残高切れ・上限・回線など）も、モックで答える |
| `ANTHROPIC_MODEL` | LLMのモデル。空なら、`claude-haiku-5-5` |

選べるモデル（値段は、100万トークンあたり。2026年11月3日時点で、最新は[公式の料金表](https://platform.claude.com/docs/en/about-claude/pricing)で確かめる）:

| モデル | `ANTHROPIC_MODEL` の値 | 入力 / 出力 | 向いているもの |
|---|---|---|---|
| Claude Haiku 5.5 | `claude-haiku-5-5`（既定） | $0.10 / $0.50 | もっとも安く、速い。このアプリの用途（条件の抽出と、1文の返答）には、これで足りる |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | $2 / $10 | 言い回しの読み取りを、より正確にしたいとき |
| Claude Opus 5.5 | `claude-opus-5-5` | $4 / $20 | さらに正確さを求めるとき。費用は、Haikuの約40倍 |
| Claude Fable 5.2 | `claude-fable-5-2` | $8 / $40 | 長時間の複雑な作業向け。この用途には、過剰 |

- 表のモデルの動作は、キーを入れたあとに、`cd backend && .venv/bin/python scripts/check_llm.py` で確かめる（送るのは、固定の例文だけ）。
- 個人情報らしき文字列は、モックでもLLMでも、AIに渡す前に伏せる。LLMに渡すのは、旅行者の文章（伏せたあと）と、読み取った条件・件数だけで、体験の内容（DB）や、予約者の個人情報は渡さない。
- キーの取得方法、費用、判断の理由は、[アーキテクチャと実装の詳細](docs/architecture.md)の5.1節と、[ADR 0007](docs/adr/0007-llm-provider.md)にある。

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

## 画面
画面は、http://localhost:5173 から開く。

旅行者の画面（ログイン不要）:

| パス | 画面 | 説明 |
|---|---|---|
| `/` | トップ | AIコンシェルジュに、文章で相談する。提案から、体験の詳細へ進む |
| `/experiences` | 体験の一覧 | 日にち・人数・エリアなどで絞り込む |
| `/experiences/:id` | 体験の詳細・予約 | 便を選び、人数と連絡先を入れて予約する |
| `/bookings/complete` | 予約の完了 | 予約番号と状態を表示する |
| `/bookings/lookup` | 予約の確認 | 予約番号と連絡先で、予約の状態を確認する |

事業者の画面（ログインが必要）:

| パス | 画面 | 説明 |
|---|---|---|
| `/admin/login` | ログイン | ログインIDとパスワードでログインする |
| `/admin/bookings` | 予約の管理 | 便ごとの予約を、承認・却下する。連絡先は、伏せ字で表示する |

## デモの手順
5分程度の流れである。**午後の便が始まる前に**、上のシードを `--reset` で入れ直し、バックエンドとフロントエンドを起動してから始める。

### 旅行者
1. トップで、「今日の午後、那覇から行ける子連れOKの体験ある？」と聞く。理由つきの提案が出る。
2. 提案の「型染めコースター体験」（承認制）の便を選び、詳細へ進む。架空の氏名・電話・メールで予約すると、「承認待ち」と予約番号が出る。番号を控える。
3. 事業者が承認したあと、「予約の確認」で、予約番号と、予約のときの電話番号（またはメール）を入れる。「確定」と表示される。連絡先を間違えると、「見つかりませんでした」になる。
4. 満席の便（「青い海のシュノーケルツアー」の、最初の便）は、「満席」で選べない。

### 事業者
1. `/admin/login` で、`demo-craft` でログインする。承認待ちの予約が、目立つ表示で見える。
2. 氏名・電話・メールは、伏せ字になっている。「連絡先を表示」を押すと、その1件だけ、全体が見える。
3. 「承認する」を押すと、状態が「確定」になる。
4. ログアウトして、`/admin/bookings` を直接開くと、ログインへ戻る。`demo-night` など、別の事業者でログインすると、その事業者の予約だけが見える。

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
| `docs/architecture.md` | アーキテクチャと実装の詳細（API、AIの仕組み、注意点） |
| `docs/product/` | プロダクトの方針・設計 |
| `docs/adr/` | 設計判断の記録 |
| `docs/summary.md` | 提出用の設計資料（要約版） |
| `docs/demo-checklist.md` | デモのチェックリストと、通した結果 |
| `docs/ai-dev-log.md` | AIとの開発の振り返り |
