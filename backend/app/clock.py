"""日時の扱い。保存はUTC、表示は日本時間とする（ADR 0002）。"""

from datetime import UTC, date, datetime, time, timedelta, timezone

# 日本には夏時間がないので、固定のオフセットで足りる（tzdata に依存しない）。
JST = timezone(timedelta(hours=9), "JST")


def utc_now() -> datetime:
    """現在の日時を、タイムゾーン付き（UTC）で返す。"""
    return datetime.now(UTC)


def jst_day_range(day: date) -> tuple[datetime, datetime]:
    """日本時間のある1日を、[開始, 終了) のタイムゾーン付きの日時で返す。

    APIの `date` は、日本時間の日付として扱う。DBはUTCで持つので、検索のときに、この範囲で絞る。
    """
    start = datetime.combine(day, time.min, tzinfo=JST)
    return start, start + timedelta(days=1)
