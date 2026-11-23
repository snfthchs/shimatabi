"""DBの接続と、SQLiteで日時・外部キーを正しく扱うための仕組み。

本格開発ではPostgreSQLに切り替える。切り替えやすくするため、DBへのアクセスはORMだけで行い、
日時はUTC・タイムゾーン付きで扱う（ADR 0002）。
"""

import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

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


def create_db_engine(url: str | None = None) -> Engine:
    """DBのエンジンを作る。`url` を省略すると、既定のSQLiteファイルを使う。"""
    if url is None:
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{DEFAULT_DB_PATH}"
    engine = create_engine(url)
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
