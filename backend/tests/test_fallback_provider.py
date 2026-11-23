"""LLMが失敗したときに、モックに切り替える、AIプロバイダーのテスト。"""

import datetime
import logging
from collections.abc import Sequence

import pytest

from app.ai.fallback import FallbackProvider
from app.ai.provider import Candidate, Conditions, Relaxation
from tests.scenario import NOW

PRIMARY_CONDITIONS = Conditions(party_size=2)
FALLBACK_CONDITIONS = Conditions(party_size=3)


class ScriptedProvider:
    """呼ばれた回数を数え、`error` があれば、それを投げるプロバイダー。"""

    def __init__(self, conditions: Conditions, reply: str, error: Exception | None = None) -> None:
        self.conditions = conditions
        self.reply = reply
        self.error = error
        self.extract_calls = 0
        self.compose_calls = 0

    def extract_conditions(self, message: str, now: datetime.datetime) -> Conditions:
        self.extract_calls += 1
        if self.error is not None:
            raise self.error
        return self.conditions

    def compose_reply(
        self,
        conditions: Conditions,
        candidates: Sequence[Candidate],
        relaxations: Sequence[Relaxation],
    ) -> str:
        self.compose_calls += 1
        if self.error is not None:
            raise self.error
        return self.reply


class StatusError(Exception):
    """HTTPのステータスコードを持つ例外（`anthropic.APIStatusError` と同じ形）。"""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make(
    primary_error: Exception | None = None,
) -> tuple[FallbackProvider, ScriptedProvider, ScriptedProvider, Clock]:
    primary = ScriptedProvider(PRIMARY_CONDITIONS, "LLMの返答", primary_error)
    fallback = ScriptedProvider(FALLBACK_CONDITIONS, "モックの返答")
    clock = Clock()
    provider = FallbackProvider(primary, fallback, cooldown_seconds=30.0, monotonic=clock)
    return provider, primary, fallback, clock


def test_the_primary_is_used_while_it_works() -> None:
    provider, primary, fallback, _ = make()

    assert provider.extract_conditions("…", NOW) == PRIMARY_CONDITIONS
    assert provider.compose_reply(Conditions(), [], []) == "LLMの返答"
    assert fallback.extract_calls == 0
    assert fallback.compose_calls == 0
    assert primary.extract_calls == 1


def test_a_failure_switches_to_the_fallback_for_the_same_call() -> None:
    provider, _, fallback, _ = make(RuntimeError("残高切れ"))

    assert provider.extract_conditions("…", NOW) == FALLBACK_CONDITIONS
    assert fallback.extract_calls == 1


def test_a_failure_in_the_reply_also_switches_to_the_fallback() -> None:
    provider, _, _, _ = make(RuntimeError("通信エラー"))

    assert provider.compose_reply(Conditions(), [], []) == "モックの返答"


def test_the_primary_is_not_called_during_the_cooldown_and_resumes_after_it() -> None:
    provider, primary, fallback, clock = make(RuntimeError("残高切れ"))

    provider.extract_conditions("…", NOW)  # 失敗する
    assert primary.extract_calls == 1

    clock.now += 10  # 待機の時間（30秒）の途中
    provider.compose_reply(Conditions(), [], [])
    provider.extract_conditions("…", NOW)
    assert primary.extract_calls == 1  # LLMは、呼ばれない
    assert primary.compose_calls == 0
    assert fallback.compose_calls == 1

    clock.now += 21  # 待機の時間が終わった
    primary.error = None
    assert provider.extract_conditions("…", NOW) == PRIMARY_CONDITIONS
    assert primary.extract_calls == 2


def test_a_failure_during_the_retry_starts_a_new_cooldown() -> None:
    provider, primary, _, clock = make(RuntimeError("残高切れ"))
    provider.extract_conditions("…", NOW)

    clock.now += 31
    provider.extract_conditions("…", NOW)  # 再び失敗する
    assert primary.extract_calls == 2

    clock.now += 5
    provider.extract_conditions("…", NOW)
    assert primary.extract_calls == 2  # 新しい待機の時間の中


def test_the_log_has_only_the_exception_type_and_the_status_never_the_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider, _, _, _ = make(StatusError("SECRET-MESSAGE: 秘密の文章", 429))
    caplog.set_level(logging.DEBUG)

    provider.extract_conditions("秘密の文章 SECRET-INPUT", NOW)

    assert "StatusError" in caplog.text
    assert "429" in caplog.text
    assert "SECRET" not in caplog.text
    assert "秘密の文章" not in caplog.text
