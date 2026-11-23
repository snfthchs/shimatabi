"""APIの入力と出力（Pydantic）。

入力は、検証と同時に、書き方をそろえる（全角・半角、電話番号のハイフンなど）。
入力の検証エラーには、入力された値を含めない（`app.errors`。個人情報を含みうるため）。
日時は、UTC（`Z` つき）で返す。画面が、日本時間に直して表示する。
"""

import datetime

from pydantic import BaseModel, Field, field_validator

from app.ai.provider import Conditions
from app.contact import EMAIL_PATTERN, PHONE_PATTERN, normalize_phone, normalize_text


class SlotOut(BaseModel):
    """便。`remaining` は残席、`is_full` は満席かどうか。"""

    id: int
    starts_at: datetime.datetime
    capacity: int
    remaining: int
    is_full: bool


class ExperienceListItem(BaseModel):
    """体験の一覧に出す、体験1件。`slots` は、条件に合う受付中の便（最大5件）。"""

    id: int
    title: str
    summary: str
    category: str
    area: str
    price_yen: int
    duration_minutes: int
    kids_ok: bool
    min_age: int | None
    rain_ok: bool
    minutes_from_naha: int
    confirmation_mode: str
    photo_url: str
    business_name: str
    slots: list[SlotOut]


class ExperienceDetail(ExperienceListItem):
    """体験の詳細。`slots` は、これから始まる受付中の便のすべて（満席のものも含む）。"""

    description: str
    meeting_point: str
    map_url: str | None


class BookingCreate(BaseModel):
    """予約の申し込み。氏名・電話・メールは、すべて必須。"""

    slot_id: int
    party_size: int = Field(ge=1, le=50)
    guest_name: str
    guest_phone: str
    guest_email: str

    @field_validator("guest_name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        value = normalize_text(value)
        if not 1 <= len(value) <= 100:
            raise ValueError("氏名は、1〜100文字で入力してください。")
        return value

    @field_validator("guest_phone")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        phone = normalize_phone(value)
        if not PHONE_PATTERN.match(phone):
            raise ValueError("電話番号の形式が正しくありません。")
        return phone

    @field_validator("guest_email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        email = normalize_text(value)
        if len(email) > 254 or not EMAIL_PATTERN.match(email):
            raise ValueError("メールアドレスの形式が正しくありません。")
        return email


class BookingCreated(BaseModel):
    """予約の作成結果。予約番号は、あとで予約を確認するときに使う。"""

    booking_number: str
    status: str
    experience_title: str
    starts_at: datetime.datetime
    party_size: int


class BookingLookup(BaseModel):
    """予約の確認の申し込み。連絡先は、予約のときに書いた電話番号またはメール。"""

    booking_number: str = Field(min_length=1, max_length=20)
    contact: str = Field(min_length=1, max_length=254)


class BookingStatusOut(BaseModel):
    """予約の確認の結果。個人情報は含めない。"""

    booking_number: str
    status: str
    experience_title: str
    starts_at: datetime.datetime
    party_size: int
    meeting_point: str


class AdminSlotOut(BaseModel):
    """事業者の管理画面に出す、便と予約の状況。"""

    id: int
    experience_id: int
    experience_title: str
    starts_at: datetime.datetime
    capacity: int
    booked_count: int
    pending_count: int  # 承認待ちの人数
    confirmed_count: int  # 確定の人数
    status: str


class AdminBookingOut(BaseModel):
    """事業者の管理画面に出す予約。氏名・電話・メールは、マスク済み。"""

    id: int
    booking_number: str
    status: str
    party_size: int
    created_at: datetime.datetime
    decided_at: datetime.datetime | None
    slot_id: int
    starts_at: datetime.datetime
    experience_title: str
    guest_name: str
    guest_phone: str
    guest_email: str


class ContactOut(BaseModel):
    """「連絡先を表示」で返す、平文の連絡先。"""

    guest_name: str
    guest_phone: str
    guest_email: str


class ConciergeRequest(BaseModel):
    """AIコンシェルジュへの相談。旅行者が自然な文章で書く。"""

    message: str = Field(min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("文章を入力してください。")
        return value


class SuggestionOut(BaseModel):
    """AIコンシェルジュの提案1件。`reason` は、DBの事実から、アプリが作った理由。"""

    experience_id: int
    title: str
    summary: str
    photo_url: str
    price_yen: int
    confirmation_mode: str
    reason: str
    slots: list[SlotOut]


class ConciergeResponse(BaseModel):
    """AIコンシェルジュの応答。入力された文章そのものは、含めない。"""

    conditions: Conditions
    suggestions: list[SuggestionOut]
    reply: str
