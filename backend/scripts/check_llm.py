"""APIキーとモデルで、LLMが実際に動くかを、1回だけ確かめる。

`.env` に `ANTHROPIC_API_KEY`（と、必要なら `ANTHROPIC_MODEL`）を書いたあとに、実行する。

    cd backend && .venv/bin/python scripts/check_llm.py

送るのは、このファイルに書いた、固定の例文だけである（個人情報は含まない）。
呼び出しは2回（条件の抽出と、返答の冒頭の1文）。料金は、Haiku 5.5 で、1円もかからない程度。

アプリ本体は、LLMが失敗しても、モックで答えるので、キーが間違っていても動き続ける。
そのため、キーの設定が合っているかは、このスクリプトで確かめる。
"""

import datetime
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import anthropic  # noqa: E402  パスを通してから読み込む
from dotenv import load_dotenv  # noqa: E402

from app.ai.llm_provider import LlmProvider  # noqa: E402
from app.ai.provider import Candidate  # noqa: E402
from app.clock import JST  # noqa: E402
from app.config import get_settings  # noqa: E402

SAMPLE_MESSAGE = "明日の午後、那覇から行ける子連れOKの体験ある？"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    settings = get_settings()
    if settings.anthropic_api_key is None:
        print(
            "ANTHROPIC_API_KEY が設定されていません。"
            "`.env` に書いてから、もう一度実行してください。"
        )
        return 1

    print(f"モデル: {settings.anthropic_model}")
    # 失敗の原因を、そのまま見るため、再試行はしない。
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=30.0, max_retries=0)
    provider = LlmProvider(client, settings.anthropic_model)
    now = datetime.datetime.now(JST)

    try:
        conditions = provider.extract_conditions(SAMPLE_MESSAGE, now)
        print(f"\n[1] 条件の抽出（例文: {SAMPLE_MESSAGE}）")
        print(conditions.model_dump_json(exclude_none=True, indent=2))

        candidate = Candidate(
            experience_id=0,
            title="（確認用の体験）",
            summary="確認用",
            reason="子連れOK・那覇から約40分",
        )
        reply = provider.compose_reply(conditions, [candidate], [])
        print("\n[2] 返答（最初の行がLLMの文。残りは、アプリのテンプレート）")
        print(reply)
    except anthropic.AuthenticationError:
        print(
            "\nAPIキーが正しくありません（401）。キーをコピーし直して、`.env` を確かめてください。"
        )
        return 1
    except anthropic.PermissionDeniedError as error:
        print(f"\nこのキーでは、使えません（403）: {error.message}")
        return 1
    except anthropic.NotFoundError:
        print("\nモデルが見つかりません（404）。`ANTHROPIC_MODEL` の値を確かめてください。")
        return 1
    except anthropic.RateLimitError as error:
        print(f"\n使用量の上限に達しています（429）: {error.message}")
        return 1
    except anthropic.APIStatusError as error:
        # 残高切れや、自分で決めた月額の上限は、400で返る。
        print(f"\nAPIがエラーを返しました（{error.status_code}）: {error.message}")
        return 1
    except anthropic.APIConnectionError:
        print("\nAPIに接続できません。回線を確かめてください。")
        return 1

    print("\nOK: LLMで動きます。アプリは、`ANTHROPIC_API_KEY` があれば、LLMで答えます。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
