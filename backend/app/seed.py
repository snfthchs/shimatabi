"""デモ用のシードデータ。すべて架空のデータである（実在の事業者・人物とは関係がない）。

使い方（`backend/` で実行する）:

    .venv/bin/python -m app.seed            # 空のDBに投入する
    .venv/bin/python -m app.seed --reset    # すべてのテーブルを消して作り直す（開発用）

デモの直前に `--reset` で作り直すと、今日の午後の便が受付中の状態になる。
今日の便は、実行した時刻より後のものだけを作る。
`APP_ENV=production` のときは、実行を拒否する。
"""

import argparse
import datetime
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.clock import JST, utc_now
from app.config import Settings, get_settings
from app.crypto import ConfigurationError
from app.db import (
    DatabaseConfigurationError,
    create_db_engine,
    init_db,
    make_session_factory,
    reset_db,
)
from app.models import (
    ACTIVE_BOOKING_STATUSES,
    Booking,
    BookingStatus,
    Business,
    BusinessUser,
    Category,
    ConfirmationMode,
    Experience,
    Slot,
    SlotStatus,
)
from app.passwords import hash_password

REPO_ROOT = Path(__file__).resolve().parents[2]

# ローカル用の、架空・デモ専用のパスワード。本番では使わない。
# 本番環境（`APP_ENV=production`）では、シードを実行できないようにしてある。
DEMO_PASSWORD = "demo-only-password"
# クラウドのデモ環境。公開している上のパスワードは使えないので、`DEMO_PASSWORD` の指定を必須にする。
CLOUD_DEMO_ENV = "cloud-demo"

# 今日から数えて、何日分の便を作るか
DAYS = 7


def _time(hour: int, minute: int = 0) -> datetime.time:
    return datetime.time(hour, minute)


@dataclass(frozen=True)
class ExperienceSpec:
    key: str  # 写真の仮のパスなどに使う識別子
    title: str
    summary: str
    description: str
    category: Category
    area: str
    meeting_point: str
    price_yen: int
    duration_minutes: int
    kids_ok: bool
    min_age: int | None
    rain_ok: bool
    minutes_from_naha: int
    confirmation_mode: ConfirmationMode
    capacity: int
    times: tuple[datetime.time, ...]  # 日本時間の開始時刻


@dataclass(frozen=True)
class BusinessSpec:
    name: str
    area: str
    login_id: str
    experiences: tuple[ExperienceSpec, ...]


@dataclass(frozen=True)
class BookingSpec:
    number: str  # 予約番号（デモで予約の確認に使える固定の値）
    experience_key: str
    day_offset: int  # 今日から何日後の便か
    time: datetime.time
    party_size: int
    status: BookingStatus
    guest_name: str
    guest_phone: str
    guest_email: str


BUSINESSES: tuple[BusinessSpec, ...] = (
    BusinessSpec(
        name="潮風マリンサービス",
        area="恩納村",
        login_id="demo-marine",
        experiences=(
            ExperienceSpec(
                key="snorkel",
                title="青い海のシュノーケルツアー",
                summary="ライフジャケット付きで、初めてでも安心。サンゴ礁と魚たちを間近で見られます。",
                description=(
                    "インストラクターが少人数で付き添い、浅瀬でシュノーケルの練習をしてから、"
                    "サンゴ礁のポイントへ向かいます。器材は貸し出します。"
                    "天候や海の状況により、中止になることがあります。"
                ),
                category=Category.MARINE,
                area="恩納村",
                meeting_point="ビーチ入口の駐車場にある、青い旗のテントに集合してください。",
                price_yen=6500,
                duration_minutes=120,
                kids_ok=True,
                min_age=6,
                rain_ok=False,
                minutes_from_naha=60,
                confirmation_mode=ConfirmationMode.INSTANT,
                capacity=8,
                times=(_time(9), _time(13)),
            ),
            ExperienceSpec(
                key="dive",
                title="体験ダイビング（はじめての方向け）",
                summary="器材もレクチャーも込み。ゆっくり海の中の世界へ。",
                description=(
                    "陸でじっくり練習をしてから、インストラクターと一緒に海へ入ります。"
                    "泳ぎが得意でなくても参加できます。天候や海の状況により、中止になることがあります。"
                ),
                category=Category.MARINE,
                area="恩納村",
                meeting_point="ダイビングショップの前に集合してください。",
                price_yen=12000,
                duration_minutes=180,
                kids_ok=False,
                min_age=10,
                rain_ok=False,
                minutes_from_naha=60,
                confirmation_mode=ConfirmationMode.INSTANT,
                capacity=4,
                times=(_time(10), _time(14)),
            ),
        ),
    ),
    BusinessSpec(
        name="島染め工房ひだまり",
        area="那覇市",
        login_id="demo-craft",
        experiences=(
            ExperienceSpec(
                key="coaster",
                title="型染めコースター体験",
                summary="好きな図案を選んで、世界にひとつのコースターを染めます。",
                description=(
                    "琉球の伝統的な型染めを、はじめての方にも分かりやすくご案内します。"
                    "作品は、その場でお持ち帰りいただけます。少人数の体験です。"
                ),
                category=Category.CRAFT,
                area="那覇市",
                meeting_point="工房の入口（青い暖簾のある建物）にお越しください。",
                price_yen=3800,
                duration_minutes=90,
                kids_ok=True,
                min_age=8,
                rain_ok=True,
                minutes_from_naha=10,
                confirmation_mode=ConfirmationMode.APPROVAL,
                capacity=4,
                times=(_time(10), _time(14)),
            ),
            ExperienceSpec(
                key="tote",
                title="型染めトートバッグ体験",
                summary="じっくり時間をかけて、自分だけのトートバッグを染めます。",
                description="図案を選び、色をのせて仕上げます。作品は、その場でお持ち帰りいただけます。",
                category=Category.CRAFT,
                area="那覇市",
                meeting_point="工房の入口（青い暖簾のある建物）にお越しください。",
                price_yen=5500,
                duration_minutes=150,
                kids_ok=False,
                min_age=12,
                rain_ok=True,
                minutes_from_naha=10,
                confirmation_mode=ConfirmationMode.APPROVAL,
                capacity=4,
                times=(_time(13),),
            ),
        ),
    ),
    BusinessSpec(
        name="やんばる星空ガイド",
        area="国頭村",
        login_id="demo-night",
        experiences=(
            ExperienceSpec(
                key="nightwalk",
                title="夜の森ナイトウォーク",
                summary="ガイドと歩く、夜の森。小さな生きものに出会えます。",
                description=(
                    "懐中電灯を片手に、少人数で夜の森を歩きます。"
                    "天候により、前日の夜に催行を判断します。歩きやすい靴でお越しください。"
                ),
                category=Category.NATURE,
                area="国頭村",
                meeting_point="道の駅の駐車場の端、案内板の前に集合してください。",
                price_yen=5000,
                duration_minutes=120,
                kids_ok=True,
                min_age=8,
                rain_ok=False,
                minutes_from_naha=120,
                confirmation_mode=ConfirmationMode.INSTANT,
                capacity=6,
                times=(_time(19, 30),),
            ),
            ExperienceSpec(
                key="stars",
                title="星空観察と島の物語",
                summary="満天の星空を眺めながら、島に伝わるお話を聞きます。",
                description="寝転んで星空を眺められる場所へご案内します。防寒具をお持ちください。",
                category=Category.NATURE,
                area="国頭村",
                meeting_point="道の駅の駐車場の端、案内板の前に集合してください。",
                price_yen=4500,
                duration_minutes=90,
                kids_ok=True,
                min_age=4,
                rain_ok=False,
                minutes_from_naha=120,
                confirmation_mode=ConfirmationMode.APPROVAL,
                capacity=8,
                times=(_time(20),),
            ),
        ),
    ),
    BusinessSpec(
        name="島ごはん教室",
        area="那覇市",
        login_id="demo-food",
        experiences=(
            ExperienceSpec(
                key="cooking",
                title="島野菜の料理教室",
                summary="島の野菜を使った家庭料理を、みんなで作って食べます。",
                description="旬の島野菜を使って、2〜3品を一緒に作ります。作った料理は、その場でいただきます。",
                category=Category.FOOD,
                area="那覇市",
                meeting_point="教室の入口（1階の看板の前）にお越しください。",
                price_yen=4200,
                duration_minutes=120,
                kids_ok=True,
                min_age=5,
                rain_ok=True,
                minutes_from_naha=10,
                confirmation_mode=ConfirmationMode.INSTANT,
                capacity=8,
                times=(_time(11), _time(15)),
            ),
            ExperienceSpec(
                key="soba",
                title="手打ち沖縄そば体験",
                summary="麺を打つところから挑戦。できたてをその場で味わえます。",
                description="生地をこねて、のばして、切るまでを体験します。作った麺は、その場でいただきます。",
                category=Category.FOOD,
                area="那覇市",
                meeting_point="教室の入口（1階の看板の前）にお越しください。",
                price_yen=3500,
                duration_minutes=90,
                kids_ok=True,
                min_age=6,
                rain_ok=True,
                minutes_from_naha=10,
                confirmation_mode=ConfirmationMode.INSTANT,
                capacity=8,
                times=(_time(10, 30), _time(15, 30)),
            ),
        ),
    ),
)

# 予約者は、すべて架空の人物。メールは `example.com`、電話番号はダミーの番号にする。
# 予約番号は、予約番号の作り方（紛らわしい文字を除いた英数字10文字）に合わせた固定の値。
BOOKINGS: tuple[BookingSpec, ...] = (
    # 満席の便（定員8名を、確定の予約2件で埋める）
    BookingSpec(
        "SEEDA23456",
        "snorkel",
        1,
        _time(9),
        4,
        BookingStatus.CONFIRMED,
        "山田 花子",
        "090-0000-0001",
        "demo-guest1@example.com",
    ),
    BookingSpec(
        "SEEDB23456",
        "snorkel",
        1,
        _time(9),
        4,
        BookingStatus.CONFIRMED,
        "佐藤 次郎",
        "090-0000-0002",
        "demo-guest2@example.com",
    ),
    # 承認待ちの予約（事業者の画面で、承認・却下をデモできる）
    BookingSpec(
        "SEEDC23456",
        "coaster",
        1,
        _time(14),
        2,
        BookingStatus.PENDING,
        "鈴木 美咲",
        "090-0000-0003",
        "demo-guest3@example.com",
    ),
    BookingSpec(
        "SEEDD23456",
        "tote",
        1,
        _time(13),
        2,
        BookingStatus.PENDING,
        "高橋 健",
        "090-0000-0004",
        "demo-guest4@example.com",
    ),
    BookingSpec(
        "SEEDE23456",
        "stars",
        1,
        _time(20),
        3,
        BookingStatus.PENDING,
        "伊藤 さくら",
        "090-0000-0005",
        "demo-guest5@example.com",
    ),
    # 確定の予約と、却下された予約（却下は定員に数えない）
    BookingSpec(
        "SEEDF23456",
        "cooking",
        1,
        _time(11),
        2,
        BookingStatus.CONFIRMED,
        "渡辺 大輔",
        "090-0000-0006",
        "demo-guest6@example.com",
    ),
    BookingSpec(
        "SEEDG23456",
        "coaster",
        2,
        _time(10),
        2,
        BookingStatus.REJECTED,
        "中村 あかり",
        "090-0000-0007",
        "demo-guest7@example.com",
    ),
)


def seed(session: Session, now: datetime.datetime, password: str = DEMO_PASSWORD) -> None:
    """デモ用のデータを投入する。コミットは、呼び出し側で行う。

    `now` は、タイムゾーン付きの現在日時。`password` は、事業者アカウントのパスワード。
    """
    today = now.astimezone(JST).date()
    slots: dict[tuple[str, int, datetime.time], Slot] = {}

    for business_spec in BUSINESSES:
        business = Business(name=business_spec.name, area=business_spec.area)
        business.users.append(
            BusinessUser(
                login_id=business_spec.login_id,
                password_hash=hash_password(password),
            )
        )
        for spec in business_spec.experiences:
            experience = Experience(
                title=spec.title,
                summary=spec.summary,
                description=spec.description,
                category=spec.category,
                area=spec.area,
                meeting_point=spec.meeting_point,
                price_yen=spec.price_yen,
                duration_minutes=spec.duration_minutes,
                kids_ok=spec.kids_ok,
                min_age=spec.min_age,
                rain_ok=spec.rain_ok,
                minutes_from_naha=spec.minutes_from_naha,
                confirmation_mode=spec.confirmation_mode,
                photo_url=f"/photos/{spec.key}.svg",  # 画像は、画面のIssueで用意する
            )
            business.experiences.append(experience)
            for offset in range(DAYS):
                for start_time in spec.times:
                    starts_at = datetime.datetime.combine(
                        today + datetime.timedelta(days=offset), start_time, tzinfo=JST
                    )
                    if starts_at <= now:
                        continue  # 過ぎた時刻の便は作らない
                    slot = Slot(
                        starts_at=starts_at,
                        capacity=spec.capacity,
                        booked_count=0,
                        status=SlotStatus.OPEN,
                    )
                    experience.slots.append(slot)
                    slots[(spec.key, offset, start_time)] = slot
        session.add(business)

    for booking_spec in BOOKINGS:
        slot = slots[(booking_spec.experience_key, booking_spec.day_offset, booking_spec.time)]
        slot.bookings.append(
            Booking(
                booking_number=booking_spec.number,
                party_size=booking_spec.party_size,
                status=booking_spec.status,
                guest_name=booking_spec.guest_name,
                guest_phone=booking_spec.guest_phone,
                guest_email=booking_spec.guest_email,
            )
        )
        # 定員を押さえるのは、承認待ちと確定の予約だけ
        if booking_spec.status in ACTIVE_BOOKING_STATUSES:
            slot.booked_count += booking_spec.party_size


class SeedError(RuntimeError):
    """シードを実行できないときのエラー。"""


def ensure_not_production(settings: Settings) -> None:
    """本番環境では、デモ用のデータを投入しない。"""
    if settings.app_env == "production":
        raise SeedError("APP_ENV=production のため、シードは実行できません。")


def demo_password(settings: Settings) -> str:
    """事業者アカウントに設定するパスワードを返す。"""
    password = settings.demo_password
    if settings.app_env == CLOUD_DEMO_ENV and (password is None or password == DEMO_PASSWORD):
        raise SeedError(
            f"APP_ENV={CLOUD_DEMO_ENV} では、公開していない値を DEMO_PASSWORD に指定してください。"
        )
    return password or DEMO_PASSWORD


def run_seed(engine: Engine, *, settings: Settings, reset: bool, now: datetime.datetime) -> None:
    """シードを実行する。`reset` なら、すべてのテーブルを消して作り直してから投入する。"""
    ensure_not_production(settings)
    password = demo_password(settings)  # DBに触る前に確認する
    if reset:
        reset_db(engine)
    else:
        init_db(engine)
    with make_session_factory(engine)() as session:
        if session.scalar(select(func.count()).select_from(Business)):
            raise SeedError("すでにデータがあります。作り直すには `--reset` をつけてください。")
        seed(session, now, password)
        session.commit()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="デモ用のシードデータを投入する（すべて架空）。")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="すべてのテーブルを消して作り直してから投入する（開発用）",
    )
    args = parser.parse_args(argv)

    # リポジトリ直下の `.env` を読む。すでに設定されている環境変数は上書きしない。
    load_dotenv(REPO_ROOT / ".env")

    try:
        settings = get_settings()
        ensure_not_production(settings)  # DBに触る前に確認する
        engine = create_db_engine(settings=settings)
        run_seed(engine, settings=settings, reset=args.reset, now=utc_now())
    except (SeedError, ConfigurationError, DatabaseConfigurationError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1

    accounts = ", ".join(business.login_id for business in BUSINESSES)
    print("シードを投入しました（すべて架空のデータです）。")
    source = (
        "環境変数 DEMO_PASSWORD の値"
        if settings.demo_password
        else "`app/seed.py` の DEMO_PASSWORD"
    )
    print(f"事業者アカウント: {accounts}（パスワードは {source}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
