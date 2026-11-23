"""ルールベースのAIプロバイダー（モック）。

LLMは使わず、キーワードと正規表現で、文章から検索条件を取り出し、テンプレートで返答を作る。
同じ約束事（`ConciergeProvider`）を満たすので、LLM版と差し替えられる。

読み取れる条件（読み取れなかったものは、None）:

- 日付: `今日`、`明日`、`あさって`、`11月30日`、`11/30`（過ぎた日付は、来年として扱う）
- 時間帯: `午前`・`朝`（6〜12時）、`午後`（12〜18時）、`夜`（18時以降）
- 人数: `2人`、`三人`、`大人2人と子供1人`（合計）、`ひとり`、`ふたり`
- 子連れ可、雨でも実施できる
- 那覇からの距離: `那覇から` → 60分以内（`30分以内`・`1時間以内` があれば、その時間）
- エリア: `恩納`、`国頭`・`やんばる`、`那覇市内`・`那覇で`
- 種類: `シュノーケル`・`海`、`染め`・`工芸`、`星`・`自然`、`料理`・`そば` など。
  複数の種類が混ざったときは、絞らない

限界: 否定（「雨じゃなければ」）や、複雑な言い回しは、読み取れない。
"""

import datetime
import re
import unicodedata
from collections.abc import Sequence

from app.ai.provider import Candidate, Conditions, Relaxation
from app.clock import JST
from app.models import Category

KIDS_WORDS = (
    "子連れ",
    "子供",
    "子ども",
    "こども",
    "家族",
    "ファミリー",
    "キッズ",
    "赤ちゃん",
    "幼児",
    "小学生",
    "園児",
)
RAIN_WORDS = ("雨", "悪天候", "荒天", "台風", "天気が悪", "天気悪", "屋内", "室内")

# 地名のキーワードと、体験に登録されているエリア名の対応
AREA_WORDS = {"恩納": "恩納村", "国頭": "国頭村", "やんばる": "国頭村", "山原": "国頭村"}

CATEGORY_WORDS: dict[Category, tuple[str, ...]] = {
    Category.MARINE: ("海", "シュノーケル", "ダイビング", "マリン", "サンゴ"),
    Category.CRAFT: ("染め", "工芸", "陶芸", "ものづくり", "手作り", "ワークショップ"),
    Category.NATURE: ("星", "自然", "ナイトウォーク", "森", "ハイキング", "トレッキング"),
    Category.FOOD: ("料理", "そば", "グルメ", "ごはん", "クッキング"),
}
CATEGORY_LABELS = {
    Category.MARINE: "海の体験",
    Category.CRAFT: "工芸の体験",
    Category.NATURE: "自然の体験",
    Category.FOOD: "食の体験",
}

KANJI_DIGITS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
MAX_PARTY_SIZE = 50
DEFAULT_MAX_MINUTES_FROM_NAHA = 60

GUIDE_TEXT = (
    "条件を読み取れませんでした。「明日の午後、子連れで行ける体験」のように、"
    "日にちや人数、行きたい場所などを教えてください。体験の一覧から探すこともできます。"
)


def _resolve_month_day(month: int, day: int, today: datetime.date) -> datetime.date | None:
    """月日から、今日以降の日付を作る。今年の日付が過ぎていれば、来年にする。"""
    for year in (today.year, today.year + 1):
        try:
            candidate = datetime.date(year, month, day)
        except ValueError:
            continue  # 存在しない日付（2月30日など）
        if candidate >= today:
            return candidate
    return None


def _extract_date(text: str, today: datetime.date) -> datetime.date | None:
    explicit = re.search(r"(\d{1,2})月(\d{1,2})日", text) or re.search(
        r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", text
    )
    if explicit:
        return _resolve_month_day(int(explicit[1]), int(explicit[2]), today)
    if "あさって" in text or "明後日" in text:
        return today + datetime.timedelta(days=2)
    if "明日" in text or "あした" in text:
        return today + datetime.timedelta(days=1)
    if any(word in text for word in ("今日", "きょう", "本日")):
        return today
    return None


def _extract_time_window(text: str) -> tuple[datetime.time | None, datetime.time | None]:
    if "午前" in text or "朝" in text:
        return datetime.time(6), datetime.time(12)
    if "午後" in text:
        return datetime.time(12), datetime.time(18)
    if "夜" in text:
        return datetime.time(18), None
    return None, None


def _extract_party_size(text: str) -> int | None:
    total = 0
    found = False
    for match in re.finditer(r"(\d+)\s*(?:人|名)", text):
        total += int(match[1])
        found = True
    for match in re.finditer(r"([一二三四五六七八九十])\s*(?:人|名)", text):
        total += KANJI_DIGITS[match[1]]
        found = True
    if not found:
        if "ひとり" in text:
            total, found = 1, True
        elif "ふたり" in text:
            total, found = 2, True
    if not found or not 1 <= total <= MAX_PARTY_SIZE:
        return None
    return total


def _extract_naha(text: str) -> tuple[str | None, int | None]:
    """那覇に関する条件。(エリア, 那覇からの移動時間の上限（分）) を返す。"""
    if re.search(r"那覇(?:市|空港)?から|那覇発", text):
        minutes = DEFAULT_MAX_MINUTES_FROM_NAHA
        limit = re.search(r"(\d+)\s*(分|時間)以内", text)
        if limit:
            minutes = int(limit[1]) * (60 if limit[2] == "時間" else 1)
        return None, minutes
    if "那覇" in text:
        return "那覇市", None
    return None, None


def _extract_area(text: str) -> str | None:
    for word, area in AREA_WORDS.items():
        if word in text:
            return area
    return None


def _extract_category(text: str) -> Category | None:
    matched = [
        category
        for category, words in CATEGORY_WORDS.items()
        if any(word in text for word in words)
    ]
    return matched[0] if len(matched) == 1 else None  # 複数の種類が混ざったときは、絞らない


def _clock(value: datetime.time) -> str:
    return f"{value.hour}:{value.minute:02d}"


def _describe_time(conditions: Conditions) -> str | None:
    window = (conditions.time_from, conditions.time_to)
    if window == (datetime.time(6), datetime.time(12)):
        return "午前"
    if window == (datetime.time(12), datetime.time(18)):
        return "午後"
    if window == (datetime.time(18), None):
        return "夜"
    if conditions.time_from and conditions.time_to:
        return f"{_clock(conditions.time_from)}〜{_clock(conditions.time_to)}"
    if conditions.time_from:
        return f"{_clock(conditions.time_from)}以降"
    if conditions.time_to:
        return f"{_clock(conditions.time_to)}まで"
    return None


def _describe(conditions: Conditions) -> str:
    """条件を、日本語の短い言葉にまとめる。例: `11月24日の午後、子連れOK、那覇から60分以内`"""
    date_part = f"{conditions.date.month}月{conditions.date.day}日" if conditions.date else None
    time_part = _describe_time(conditions)
    head = f"{date_part}の{time_part}" if date_part and time_part else date_part or time_part
    parts = [
        head,
        f"{conditions.party_size}人" if conditions.party_size else None,
        "子連れOK" if conditions.kids_ok else None,
        "雨でも楽しめる" if conditions.rain_ok else None,
        conditions.area,
        (
            f"那覇から{conditions.max_minutes_from_naha}分以内"
            if conditions.max_minutes_from_naha is not None
            else None
        ),
        CATEGORY_LABELS[conditions.category] if conditions.category else None,
    ]
    return "、".join(part for part in parts if part)


class MockProvider:
    """ルールベースの `ConciergeProvider`。"""

    def extract_conditions(self, message: str, now: datetime.datetime) -> Conditions:
        text = unicodedata.normalize("NFKC", message)  # 全角の数字・記号を、半角にそろえる
        today = now.astimezone(JST).date()
        naha_area, max_minutes = _extract_naha(text)
        time_from, time_to = _extract_time_window(text)
        return Conditions(
            date=_extract_date(text, today),
            time_from=time_from,
            time_to=time_to,
            party_size=_extract_party_size(text),
            kids_ok=True if any(word in text for word in KIDS_WORDS) else None,
            rain_ok=True if any(word in text for word in RAIN_WORDS) else None,
            area=_extract_area(text) or naha_area,
            max_minutes_from_naha=max_minutes,
            category=_extract_category(text),
        )

    def compose_reply(
        self,
        conditions: Conditions,
        candidates: Sequence[Candidate],
        relaxations: Sequence[Relaxation],
    ) -> str:
        if conditions.is_empty():
            return GUIDE_TEXT
        summary = _describe(conditions)
        if candidates:
            lines = [f"{summary}という条件で、{len(candidates)}件の体験が見つかりました。"]
            lines += [f"・{candidate.title}（{candidate.reason}）" for candidate in candidates]
            lines.append("気になる体験を選ぶと、便を選んで予約できます。")
            return "\n".join(lines)
        lines = [f"{summary}という条件に合う体験は、見つかりませんでした。"]
        if relaxations:
            lines.append("条件を緩めると、見つかるかもしれません。")
            lines += [
                f"・{relaxation.label}を外すと、{relaxation.result_count}件あります"
                for relaxation in relaxations
            ]
        else:
            lines.append("条件を変えて、もう一度お試しください。体験の一覧から探すこともできます。")
        return "\n".join(lines)
