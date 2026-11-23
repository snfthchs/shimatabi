"""設定から、AIプロバイダーを選ぶ。

`ANTHROPIC_API_KEY` が設定されていれば、LLM（Claude）を使い、失敗したときは、モックに切り替える。
設定されていなければ、ルールベースのモックだけを使う（キーのない環境でも、AI相談が動く）。
"""

from functools import lru_cache

import anthropic

from app.ai.fallback import FallbackProvider
from app.ai.llm_provider import LlmProvider
from app.ai.mock_provider import MockProvider
from app.ai.provider import ConciergeProvider
from app.config import Settings

# LLMの応答を待つ時間（秒）と、失敗したときの再試行の回数。デモで、長く待たせないために短くする。
# 再試行を入れると、最悪の待ちが倍になる。失敗はモックに切り替えるので、再試行はしない。
LLM_TIMEOUT_SECONDS = 15.0
LLM_MAX_RETRIES = 0


@lru_cache(maxsize=4)
def _build_llm_provider(api_key: str, model: str) -> LlmProvider:
    """LLMプロバイダーを作る。通信の準備（クライアント）を、使い回すため、同じ値なら1つだけ作る。"""
    client = anthropic.Anthropic(
        api_key=api_key, timeout=LLM_TIMEOUT_SECONDS, max_retries=LLM_MAX_RETRIES
    )
    return LlmProvider(client, model)


@lru_cache(maxsize=4)
def _build_fallback_provider(api_key: str, model: str) -> FallbackProvider:
    """失敗の記録（待機の時間）を、リクエストをまたいで持つため、同じ値なら1つだけ作る。"""
    return FallbackProvider(_build_llm_provider(api_key, model), MockProvider())


def get_provider(settings: Settings) -> ConciergeProvider:
    """設定に合った、AIプロバイダーを返す。"""
    if settings.anthropic_api_key is None:
        return MockProvider()
    return _build_fallback_provider(settings.anthropic_api_key, settings.anthropic_model)


def describe_provider(settings: Settings) -> str:
    """起動のときに、ログへ出す説明。キーは含めない。"""
    if settings.anthropic_api_key is None:
        return "AIコンシェルジュ: ルールベースのモック（ANTHROPIC_API_KEY が未設定）"
    return (
        f"AIコンシェルジュ: LLM（モデル: {settings.anthropic_model}）。"
        "失敗したときは、モックで答えます"
    )
