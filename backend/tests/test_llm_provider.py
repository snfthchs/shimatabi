"""LLMプロバイダーのテスト。偽のクライアントを使うので、通信も課金もしない。"""

import datetime
import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic import ValidationError

from app.ai.llm_provider import (
    AREAS,
    CONDITIONS_SCHEMA,
    MAX_OPENING_LENGTH,
    LlmError,
    LlmProvider,
    conditions_from_json,
)
from app.ai.mock_provider import GUIDE_TEXT, MockProvider
from app.ai.provider import Candidate, Conditions, Relaxation
from app.models import Category
from tests.scenario import NOW


@dataclass
class FakeBlock:
    type: str
    text: str = ""


@dataclass
class FakeResponse:
    content: list[FakeBlock]
    stop_reason: str = "end_turn"


def text_response(text: str, stop_reason: str = "end_turn") -> FakeResponse:
    return FakeResponse([FakeBlock("text", text)], stop_reason)


@dataclass
class FakeMessages:
    """`client.messages` の偽物。決めた応答を順に返し、呼ばれた引数を記録する。"""

    responses: list[FakeResponse | Exception]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@dataclass
class FakeClient:
    messages: FakeMessages


def make_provider(
    *responses: FakeResponse | Exception, model: str = "test-model"
) -> tuple[LlmProvider, FakeMessages]:
    messages = FakeMessages(list(responses))
    return LlmProvider(FakeClient(messages), model), messages


ALL_NULL: dict[str, Any] = {
    "date": None,
    "time_from": None,
    "time_to": None,
    "party_size": None,
    "kids_ok": None,
    "rain_ok": None,
    "area": None,
    "max_minutes_from_naha": None,
    "category": None,
}


def conditions_json(**values: Any) -> str:
    return json.dumps({**ALL_NULL, **values})


CANDIDATE = Candidate(
    experience_id=1,
    title="秘密の洞窟ツアー",
    summary="地元ガイドと歩く、静かな洞窟の概要",
    reason="子連れOK・那覇から約40分・11/24 13:00の便は残り4席",
)


# ---- 条件の抽出 ----


def test_extract_conditions_sends_the_message_the_date_and_a_json_schema() -> None:
    provider, messages = make_provider(text_response(conditions_json()), model="my-model")

    provider.extract_conditions("明日の午後、子連れで海", NOW)

    assert len(messages.calls) == 1
    call = messages.calls[0]
    assert call["model"] == "my-model"
    assert call["max_tokens"] > 0
    user_content = call["messages"][0]["content"]
    assert "2026-11-24（火曜日）" in user_content  # 今日の日付（相対的な言い方を、計算するため）
    assert "<message>\n明日の午後、子連れで海\n</message>" in user_content
    assert call["output_config"]["effort"] == "low"
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": CONDITIONS_SCHEMA}
    assert "従いません" in call["system"]  # 文章の中の指示には、従わない


def test_extract_conditions_does_not_send_anything_but_the_message_and_the_date() -> None:
    provider, messages = make_provider(text_response(conditions_json()))

    provider.extract_conditions("明日の午後", NOW)

    call = messages.calls[0]
    assert set(call) == {"model", "max_tokens", "system", "messages", "output_config"}
    assert len(call["messages"]) == 1
    assert call["messages"][0]["role"] == "user"


def test_extract_conditions_maps_the_json_to_conditions() -> None:
    provider, _ = make_provider(
        text_response(
            conditions_json(
                date="2026-11-25",
                time_from="12:00",
                time_to="18:00",
                party_size=3,
                kids_ok=True,
                rain_ok=True,
                area="恩納村",
                max_minutes_from_naha=45,
                category="marine",
            )
        )
    )

    conditions = provider.extract_conditions("…", NOW)

    assert conditions == Conditions(
        date=datetime.date(2026, 11, 25),
        time_from=datetime.time(12, 0),
        time_to=datetime.time(18, 0),
        party_size=3,
        kids_ok=True,
        rain_ok=True,
        area="恩納村",
        max_minutes_from_naha=45,
        category=Category.MARINE,
    )


def test_unreadable_items_stay_empty() -> None:
    provider, _ = make_provider(text_response(conditions_json()))

    assert provider.extract_conditions("こんにちは", NOW).is_empty()


def test_false_flags_are_treated_as_not_specified() -> None:
    # True のときだけ、絞り込む（False は、「絞らない」と同じ）
    conditions = conditions_from_json(conditions_json(kids_ok=False, rain_ok=False))

    assert conditions.kids_ok is None
    assert conditions.rain_ok is None
    assert conditions.is_empty()


def test_an_unknown_area_is_ignored() -> None:
    assert conditions_from_json(conditions_json(area="東京都")).area is None
    assert conditions_from_json(conditions_json(area="那覇市")).area == "那覇市"
    assert set(AREAS) == {"那覇市", "恩納村", "国頭村"}


@pytest.mark.parametrize(
    "values",
    [
        {"party_size": 0},
        {"party_size": 51},
        {"max_minutes_from_naha": -1},
    ],
)
def test_out_of_range_values_are_rejected(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        conditions_from_json(conditions_json(**values))


@pytest.mark.parametrize(
    "text",
    [
        "これはJSONではありません",
        "[]",
        conditions_json(date="2026年11月25日"),
        conditions_json(time_from="午後"),
        conditions_json(category="unknown"),
    ],
)
def test_a_malformed_answer_is_an_error(text: str) -> None:
    provider, _ = make_provider(text_response(text))

    with pytest.raises((ValueError, LlmError, ValidationError)):
        provider.extract_conditions("…", NOW)


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens", "pause_turn"])
def test_an_answer_that_did_not_finish_is_an_error(stop_reason: str) -> None:
    provider, _ = make_provider(text_response(conditions_json(), stop_reason))

    with pytest.raises(LlmError):
        provider.extract_conditions("…", NOW)


def test_an_answer_without_text_is_an_error() -> None:
    provider, _ = make_provider(FakeResponse([FakeBlock("thinking")]))

    with pytest.raises(LlmError):
        provider.extract_conditions("…", NOW)


def test_errors_never_include_the_message() -> None:
    provider, _ = make_provider(text_response("壊れた応答 SECRET-ANSWER", "refusal"))

    with pytest.raises(LlmError) as error:
        provider.extract_conditions("秘密の文章 SECRET-INPUT", NOW)

    assert "SECRET-INPUT" not in str(error.value)
    assert "SECRET-ANSWER" not in str(error.value)


def test_client_errors_are_raised_to_the_caller() -> None:
    provider, _ = make_provider(RuntimeError("通信エラー"))

    with pytest.raises(RuntimeError):
        provider.extract_conditions("…", NOW)


# ---- 返答の冒頭の1文 ----

CONDITIONS = Conditions(date=datetime.date(2026, 11, 25), kids_ok=True)


def test_compose_reply_replaces_only_the_first_line_of_the_template() -> None:
    provider, _ = make_provider(text_response("明日、子連れで行ける体験が、1件見つかりました。"))
    candidates = [CANDIDATE]

    reply = provider.compose_reply(CONDITIONS, candidates, [])

    template = MockProvider().compose_reply(CONDITIONS, candidates, []).split("\n")
    lines = reply.split("\n")
    assert lines[0] == "明日、子連れで行ける体験が、1件見つかりました。"
    assert lines[1:] == template[1:]  # 候補の一覧と、締めの案内は、アプリのテンプレート
    assert "秘密の洞窟ツアー" in reply


def test_compose_reply_sends_only_the_conditions_and_the_count_not_the_candidates() -> None:
    provider, messages = make_provider(text_response("見つかりました。"))

    provider.compose_reply(CONDITIONS, [CANDIDATE], [Relaxation("雨の条件", 2)])

    call = messages.calls[0]
    sent = json.dumps(call["messages"], ensure_ascii=False) + call["system"]
    assert json.loads(call["messages"][0]["content"]) == {
        "読み取った条件": {"date": "2026-11-25", "kids_ok": True},
        "見つかった件数": 1,
    }
    # 体験の名前・概要・理由（DBの内容）は、LLMに渡さない
    assert CANDIDATE.title not in sent
    assert CANDIDATE.summary not in sent
    assert CANDIDATE.reason not in sent
    assert "雨の条件" not in sent
    assert call["output_config"] == {"effort": "low"}


def test_compose_reply_for_no_results_keeps_the_relaxation_suggestions() -> None:
    provider, messages = make_provider(text_response("条件に合う体験は、見つかりませんでした。"))
    relaxations = [Relaxation("雨の条件", 2)]

    reply = provider.compose_reply(CONDITIONS, [], relaxations)

    assert reply.split("\n")[0] == "条件に合う体験は、見つかりませんでした。"
    assert "雨の条件を外すと、2件あります" in reply
    assert json.loads(messages.calls[0]["messages"][0]["content"])["見つかった件数"] == 0


def test_compose_reply_does_not_call_the_llm_when_no_condition_was_read() -> None:
    provider, messages = make_provider()

    assert provider.compose_reply(Conditions(), [], []) == GUIDE_TEXT
    assert messages.calls == []


@pytest.mark.parametrize(
    "opening",
    ["1行目\n2行目", "あ" * (MAX_OPENING_LENGTH + 1)],
)
def test_an_opening_that_is_not_one_short_line_is_an_error(opening: str) -> None:
    provider, _ = make_provider(text_response(opening))

    with pytest.raises(LlmError):
        provider.compose_reply(CONDITIONS, [CANDIDATE], [])


def test_a_refused_reply_is_an_error() -> None:
    provider, _ = make_provider(text_response("お答えできません", "refusal"))

    with pytest.raises(LlmError):
        provider.compose_reply(CONDITIONS, [CANDIDATE], [])
