"""旅行者向け: AIコンシェルジュ（`/api/concierge`）。認証は不要。

旅行者の「探す入口」。自然な文章から条件を取り出し、DBにある体験を提案する。
**予約は、実行しない。** 提案から、体験の詳細・予約の画面へ進む。
"""

from fastapi import APIRouter, Response

from app.deps import NowDep, ProviderDep, SessionDep
from app.routers.experiences import slot_out
from app.schemas import ConciergeRequest, ConciergeResponse, SuggestionOut
from app.services.concierge import Suggestion, run_concierge

router = APIRouter(prefix="/api/concierge", tags=["concierge"])


def _suggestion_out(suggestion: Suggestion) -> SuggestionOut:
    experience = suggestion.experience
    return SuggestionOut(
        experience_id=experience.id,
        title=experience.title,
        summary=experience.summary,
        photo_url=experience.photo_url,
        price_yen=experience.price_yen,
        confirmation_mode=experience.confirmation_mode,
        reason=suggestion.reason,
        slots=[slot_out(slot) for slot in suggestion.slots],
    )


@router.post("/search", response_model=ConciergeResponse)
def search(
    body: ConciergeRequest,
    session: SessionDep,
    now: NowDep,
    provider: ProviderDep,
    response: Response,
) -> ConciergeResponse:
    """文章から条件を取り出し、条件に合う、受付中の便を持つ体験を提案する。"""
    result = run_concierge(session, provider, body.message, now)
    # 入力された文章は、ログにも、応答にも含めない。
    response.headers["Cache-Control"] = "no-store"
    return ConciergeResponse(
        conditions=result.conditions,
        suggestions=[_suggestion_out(suggestion) for suggestion in result.suggestions],
        reply=result.reply,
    )
