"""DBの接続と、SQLiteで日時・外部キーを正しく扱うための仕組み。

ローカルはSQLite、クラウドはPostgreSQLを使う。どちらでも動くように、DBへのアクセスは
ORMだけで行い、日時はUTC・タイムゾーン付きで扱う（ADR 0002）。
"""

import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import URL, DateTime, Engine, create_engine, event
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import Settings, get_settings

# DBファイルの場所（`backend/data/shimatabi.db`。`.gitignore` 済み）
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "shimatabi.db"


class Base(DeclarativeBase):
    """すべてのモデルの土台。"""


class UTCDateTime(TypeDecorator[datetime.datetime]):
    """タイムゾーン付きの日時を、UTCに直して保存する型。

    SQLiteの日時は、タイムゾーンを持たない文字列として保存される。そのため、
    保存するときにUTCに直してタイムゾーンを外し、読み出すときにUTCを付け直す。
    タイムゾーンのない日時は、取り違えを防ぐため、エラーにする。
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime.datetime | None, dialect: Dialect
    ) -> datetime.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise TypeError(
                "日時にはタイムゾーンが必要です（UTCまたは日本時間などで渡してください）。"
            )
        return value.astimezone(datetime.UTC).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime.datetime | None, dialect: Dialect
    ) -> datetime.datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=datetime.UTC)


def _enable_sqlite_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
    # SQLiteは、既定では外部キーの制約を確認しない。接続のたびに有効にする。
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class DatabaseConfigurationError(RuntimeError):
    """DBの接続の設定が足りない、または不正なときのエラー。値は、メッセージに含めない。"""


def generate_iam_auth_token(host: str, port: int, user: str, region: str) -> str:
    """IAMのデータベース認証で、パスワードの代わりに使う短命のトークンを作る。"""
    import boto3  # クラウドでだけ使うため、ここで読み込む

    client = boto3.client("rds", region_name=region)
    token: str = client.generate_db_auth_token(DBHostname=host, Port=port, DBUsername=user)
    return token


def create_postgres_engine(settings: Settings) -> Engine:
    """PostgreSQLのエンジンを作る。接続は暗号化し、既定ではサーバー証明書を検証する。"""
    host, port, name, user = (
        settings.db_host,
        settings.db_port,
        settings.db_name,
        settings.db_user,
    )
    if host is None or name is None or user is None:
        raise DatabaseConfigurationError("DB_HOST、DB_NAME、DB_USER を指定してください。")
    if settings.db_auth not in ("iam", "password"):
        raise DatabaseConfigurationError("DB_AUTH は、iam か password を指定してください。")
    if settings.db_auth == "password" and settings.db_password is None:
        raise DatabaseConfigurationError("DB_AUTH=password では、DB_PASSWORD が必要です。")
    region = settings.aws_region
    if settings.db_auth == "iam" and region is None:
        raise DatabaseConfigurationError("DB_AUTH=iam では、AWS_REGION が必要です。")

    connect_args: dict[str, Any] = {"sslmode": settings.db_sslmode, "connect_timeout": 10}
    if settings.db_ssl_root_cert is not None:
        connect_args["sslrootcert"] = settings.db_ssl_root_cert
    url = URL.create(
        "postgresql+psycopg",
        username=user,
        password=settings.db_password if settings.db_auth == "password" else None,
        host=host,
        port=port,
        database=name,
    )
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True, pool_recycle=600)

    if settings.db_auth == "iam":
        assert region is not None

        # トークンは短時間で切れるため、新しい接続を作るたびに取得する。
        def _set_token(dialect: Any, record: Any, cargs: Any, cparams: Any) -> None:
            cparams["password"] = generate_iam_auth_token(host, port, user, region)

        event.listen(engine, "do_connect", _set_token)
    return engine


def create_db_engine(url: str | None = None, settings: Settings | None = None) -> Engine:
    """DBのエンジンを作る。

    `url` を省略すると、環境変数に `DB_HOST` があればPostgreSQL、なければ既定の
    SQLiteファイルを使う。
    """
    if url is None:
        settings = settings or get_settings()
        if settings.db_host is not None:
            return create_postgres_engine(settings)
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{DEFAULT_DB_PATH}"
    # SQLiteは、同時に書き込めるのは1つだけ。ほかの書き込みが終わるのを、最大30秒待つ
    # （待たずに「database is locked」で失敗するのを防ぐ）。
    connect_args = {"timeout": 30} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """セッション（DBとのやり取りの単位）を作る関数を返す。"""
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """テーブルがなければ作る。マイグレーションのツールは、本格開発で導入する。"""
    from app import models  # noqa: F401  モデルを登録するために読み込む

    Base.metadata.create_all(engine)


def reset_db(engine: Engine) -> None:
    """すべてのテーブルを消して作り直す。開発用（シードの `--reset` で使う）。"""
    from app import models  # noqa: F401  モデルを登録するために読み込む

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
