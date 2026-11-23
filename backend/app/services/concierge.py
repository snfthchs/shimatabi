"""AIコンシェルジュの流れ（`docs/product/design-overview.md` の6章）。

    旅行者の文章 → ①条件の抽出（AIプロバイダー）→ ②検索（アプリ）→ ③返答文の生成（AIプロバイダー）

- **検索は、AIに任せない。** `app.services.experience_search` で、DBから探す。そのため、
  提案は、必ずDBにある体験と、受付中の便だけになる。
- **提案の理由は、AIではなく、アプリが、DBの事実から作る**（子連れ可、那覇からの時間、残席など）。
  AIの文章に、事実を作らせない。
- **AIに渡す前に、旅行者の文章から、個人情報らしき文字列（電話番号・メールなど）を、印に置き換える**
  （`app.ai.pii_guard`。モックにも、LLMにも、同じ処理を通す。`docs/adr/0007-llm-provider.md`）。
- AIプロバイダーが失敗したときは、一覧へ誘導する（失敗に備える）。
- 旅行者の文章は、**ログに残さない**。ログに出すのは、例外の種類だけ。
"""

import datetime
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.pii_guard import mask_personal_info
from app.ai.provider import Candidate, ConciergeProvider, Conditions, Relaxation
from app.clock import JST
from app.models import ConfirmationMode, Experience, Slot
from app.services.experience_search import SearchCriteria, remaining_seats, search_experiences

logger = logging.getLogger(__name__)

MAX_SUGGESTIONS = 5  # 提案する体験の数の上限
SLOTS_PER_SUGGESTION = 3  # 体験ごとに載せる便の数の上限
MAX_RELAXATIONS = 3  # 0件のとき、提案する緩め方の数の上限

# AIプロバイダーが失敗したときの、決まった文面
FALLBACK_REPLY_FOUND = "条件に合う体験を表示します。気になる体験を選ぶと、便を選んで予約できます。"
FALLBACK_REPLY_NOT_FOUND = "うまく読み取れませんでした。体験の一覧から探してみてください。"

# 0件のとき、外してみる条件。外しても意味が通りやすい順（外すと広がる順）に並べる。
_RELAXABLE_CONDITIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("雨の条件", ("rain_ok",)),
    ("子連れの条件", ("kids_ok",)),
    ("種類の条件", ("category",)),
    ("エリアの条件", ("area",)),
    ("那覇からの距離の条件", ("max_minutes_from_naha",)),
    ("時間帯の条件", ("time_from", "time_to")),
    ("人数の条件", ("party_size",)),
    ("日付の条件", ("date",)),
)


@dataclass(frozen=True)
class Suggestion:
    """提案の1件。体験と、条件に合う受付中の便と、選んだ理由。"""

    experience: Experience
    slots: list[Slot]
    reason: str


@dataclass(frozen=True)
class ConciergeResult:
    conditions: Conditions
    suggestions: list[Suggestion]
    reply: str
    # 旅行者の文章に、個人情報らしき文字列があり、AIに渡す前に伏せたか。
    pii_masked: bool = False


def _to_criteria(conditions: Conditions) -> SearchCriteria:
    return SearchCriteria(
        date=conditions.date,
        time_from=conditions.time_from,
        time_to=conditions.time_to,
        party_size=conditions.party_size or 1,
        kids_ok=conditions.kids_ok,
        rain_ok=conditions.rain_ok,
        area=conditions.area,
        category=conditions.category.value if conditions.category else None,
        max_minutes_from_naha=conditions.max_minutes_from_naha,
    )


def build_reason(experience: Experience, slots: list[Slot]) -> str:
    """提案の理由を、DBの事実から作る。

    例: `子連れOK・那覇から約40分・11/24 13:00の便は残り4席・予約はすぐ確定`
    """
    parts: list[str] = []
    if experience.kids_ok:
        parts.append("子連れOK")
    if experience.rain_ok:
        parts.append("雨でも実施")
    parts.append(f"那覇から約{experience.minutes_from_naha}分")
    first = slots[0]
    start = first.starts_at.astimezone(JST)
    when = f"{start.month}/{start.day} {start.hour}:{start.minute:02d}"
    parts.append(f"{when}の便は残り{remaining_seats(first)}席")
    if experience.confirmation_mode == ConfirmationMode.INSTANT:
        parts.append("予約はすぐ確定")
    else:
        parts.append("予約は事業者の承認後に確定")
    return "・".join(parts)


def _find_relaxations(
    session: Session, conditions: Conditions, now: datetime.datetime
) -> list[Relaxation]:
    """条件を1つずつ外して、DBで再検索し、件数のある外し方だけを返す。"""
    found: list[Relaxation] = []
    for label, fields in _RELAXABLE_CONDITIONS:
        if all(getattr(conditions, field) is None for field in fields):
            continue  # もともと指定されていない条件は、外せない
        relaxed = conditions.model_copy(update={field: None for field in fields})
        results = search_experiences(session, _to_criteria(relaxed), now, slots_per_experience=1)
        if results:
            found.append(Relaxation(label=label, result_count=len(results)))
        if len(found) >= MAX_RELAXATIONS:
            break
    return found


def _extract_conditions(
    provider: ConciergeProvider, message: str, now: datetime.datetime
) -> Conditions:
    try:
        return provider.extract_conditions(message, now)
    except Exception as error:
        # 旅行者の文章は、個人情報を含みうるので、ログに出さない。例外の種類だけを残す。
        logger.warning("条件の抽出に失敗しました（例外の種類: %s）", type(error).__name__)
        return Conditions()


def _compose_reply(
    provider: ConciergeProvider,
    conditions: Conditions,
    candidates: list[Candidate],
    relaxations: list[Relaxation],
) -> str:
    try:
        return provider.compose_reply(conditions, candidates, relaxations)
    except Exception as error:
        logger.warning("返答文の生成に失敗しました（例外の種類: %s）", type(error).__name__)
        return FALLBACK_REPLY_FOUND if candidates else FALLBACK_REPLY_NOT_FOUND


def run_concierge(
    session: Session, provider: ConciergeProvider, message: str, now: datetime.datetime
) -> ConciergeResult:
    """旅行者の文章から、体験を提案する。

    条件が1つも読み取れないときは、検索せずに、一覧へ誘導する返答だけを返す。
    条件に合う便がないときは、条件を緩める提案（件数のあるものだけ）を返答に含める。
    """
    # 個人情報らしき文字列は、AIに渡す前に伏せる。AIには、伏せたあとの文章だけを渡す。
    masked = mask_personal_info(message)
    conditions = _extract_conditions(provider, masked.text, now)

    suggestions: list[Suggestion] = []
    relaxations: list[Relaxation] = []
    if not conditions.is_empty():
        results = search_experiences(
            session, _to_criteria(conditions), now, slots_per_experience=SLOTS_PER_SUGGESTION
        )
        suggestions = [
            Suggestion(
                result.experience, result.slots, build_reason(result.experience, result.slots)
            )
            for result in results[:MAX_SUGGESTIONS]
        ]
        if not suggestions:
            relaxations = _find_relaxations(session, conditions, now)

    candidates = [
        Candidate(
            experience_id=suggestion.experience.id,
            title=suggestion.experience.title,
            summary=suggestion.experience.summary,
            reason=suggestion.reason,
        )
        for suggestion in suggestions
    ]
    reply = _compose_reply(provider, conditions, candidates, relaxations)
    return ConciergeResult(
        conditions=conditions,
        suggestions=suggestions,
        reply=reply,
        pii_masked=masked.masked,
    )
