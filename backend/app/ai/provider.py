"""AIコンシェルジュの、AIプロバイダーの約束事（`docs/product/design-overview.md` の6章）。

AIコンシェルジュは、旅行者の「探す入口」である。AIが担当するのは、次の2つだけ。

1. 条件の抽出: 旅行者の文章から、検索条件（`Conditions`）を取り出す
2. 返答文の生成: 検索の結果（候補）をもとに、返答の文章を作る

**検索そのものと、予約は、AIに任せない。** 検索は、アプリの通常の処理（DBの検索）で行う。
そのため、提案は、必ずDBにある体験と、受付中の便だけになる（存在しない体験を提案しない）。

プロバイダーは、差し替えられる。まず、ルールベースのモック（`MockProvider`）で作る。
LLM APIへの接続は、同じ約束事を満たす別の実装として、あとから足す。LLMが出した条件は、
`Conditions` で検証してから使う（形が正しくなければ、使わない）。

AIに渡すのは、旅行者の文章と、現在時刻だけ。予約者の個人情報は、渡さない。
"""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from app.models import Category


class Conditions(BaseModel):
    """文章から取り出した、検索条件。すべて省略できる（読み取れなかった条件は、None）。"""

    date: datetime.date | None = None  # 日本時間の日付
    time_from: datetime.time | None = None  # 日本時間の時刻（この時刻以降の便）
    time_to: datetime.time | None = None  # 日本時間の時刻（この時刻より前の便）
    party_size: int | None = Field(default=None, ge=1, le=50)
    kids_ok: bool | None = None  # True のときだけ、子連れ可に絞る
    rain_ok: bool | None = None  # True のときだけ、雨でも実施できるものに絞る
    area: str | None = None
    max_minutes_from_naha: int | None = Field(default=None, ge=0)
    category: Category | None = None

    def is_empty(self) -> bool:
        """条件が、1つも読み取れていないか。"""
        return not self.model_dump(exclude_none=True)


@dataclass(frozen=True)
class Candidate:
    """返答文に載せる、候補の体験。`reason` は、DBの事実から、アプリが作った理由。"""

    experience_id: int
    title: str
    summary: str
    reason: str


@dataclass(frozen=True)
class Relaxation:
    """条件を1つ外したときの、検索結果の件数。0件のときの提案に使う。"""

    label: str  # 外す条件の名前（例: 「雨の条件」）
    result_count: int


class ConciergeProvider(Protocol):
    """AIプロバイダー。モックも、LLM版も、この約束事を満たす。"""

    def extract_conditions(self, message: str, now: datetime.datetime) -> Conditions:
        """旅行者の文章から、検索条件を取り出す。`now` は、タイムゾーン付きの現在日時。"""
        ...

    def compose_reply(
        self,
        conditions: Conditions,
        candidates: Sequence[Candidate],
        relaxations: Sequence[Relaxation],
    ) -> str:
        """返答の文章を作る。

        - 候補があるとき: 条件の要約と、候補を紹介する
        - 候補が0件のとき: `relaxations`（件数のある緩め方）を提案する
        - 条件が1つも読み取れていないとき: 体験の一覧へ誘導する
        """
        ...
