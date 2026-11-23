"""LLMが失敗したときに、モックに切り替える、AIプロバイダー。

デモの最中に、残高切れ・月額の上限・回線の不調・LLMの拒否などが起きても、AI相談を止めない
ためである（`docs/adr/0007-llm-provider.md`）。

失敗したあとは、一定の時間、LLMを呼ばずに、モックで答える。失敗が続くとき（残高切れなど）に、
毎回、LLMの待ち時間を使わないようにするため。

旅行者の文章は、ログに出さない。ログに出すのは、例外の種類と、HTTPのステータスコードだけ。
"""

import datetime
import logging
import time
from collections.abc import Callable, Sequence

from app.ai.provider import Candidate, ConciergeProvider, Conditions, Relaxation

logger = logging.getLogger("uvicorn.error")

# 失敗したあと、LLMを呼ばずに、モックで答える時間（秒）
COOLDOWN_SECONDS = 30.0


class FallbackProvider:
    """`primary`（LLM）を使い、失敗したら `fallback`（モック）で答える。"""

    def __init__(
        self,
        primary: ConciergeProvider,
        fallback: ConciergeProvider,
        *,
        cooldown_seconds: float = COOLDOWN_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._cooldown_seconds = cooldown_seconds
        self._monotonic = monotonic
        self._resume_at = 0.0

    def _primary_is_available(self) -> bool:
        return self._monotonic() >= self._resume_at

    def _note_failure(self, error: Exception, action: str) -> None:
        self._resume_at = self._monotonic() + self._cooldown_seconds
        # 入力した文章は、個人情報を含みうるので、出さない。
        logger.warning(
            "LLMでの%sに失敗したため、モックで答えます（例外の種類: %s、ステータス: %s）",
            action,
            type(error).__name__,
            getattr(error, "status_code", None),
        )

    def extract_conditions(self, message: str, now: datetime.datetime) -> Conditions:
        if self._primary_is_available():
            try:
                return self._primary.extract_conditions(message, now)
            except Exception as error:
                self._note_failure(error, "条件の抽出")
        return self._fallback.extract_conditions(message, now)

    def compose_reply(
        self,
        conditions: Conditions,
        candidates: Sequence[Candidate],
        relaxations: Sequence[Relaxation],
    ) -> str:
        if self._primary_is_available():
            try:
                return self._primary.compose_reply(conditions, candidates, relaxations)
            except Exception as error:
                self._note_failure(error, "返答文の生成")
        return self._fallback.compose_reply(conditions, candidates, relaxations)
