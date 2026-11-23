"""日時の扱い。保存はUTC、表示は日本時間とする（ADR 0002）。"""

from datetime import UTC, datetime, timedelta, timezone

# 日本には夏時間がないので、固定のオフセットで足りる（tzdata に依存しない）。
JST = timezone(timedelta(hours=9), "JST")


def utc_now() -> datetime:
    """現在の日時を、タイムゾーン付き（UTC）で返す。"""
    return datetime.now(UTC)
