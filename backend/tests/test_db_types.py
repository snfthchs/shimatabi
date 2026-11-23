import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.dialects import sqlite
from sqlalchemy.orm import Session

from app.clock import JST
from app.db import UTCDateTime
from app.models import Slot
from tests.factories import create_business, create_experience, create_slot


def test_aware_datetime_round_trips_as_utc(session: Session) -> None:
    experience = create_experience(session, create_business(session))
    jst_time = datetime.datetime(2026, 11, 24, 9, 0, tzinfo=JST)
    slot = create_slot(session, experience, starts_at=jst_time)
    session.commit()

    session.expire_all()  # 保持している値を捨てて、DBから読み直す
    loaded = session.get(Slot, slot.id)

    assert loaded is not None
    assert loaded.starts_at == jst_time  # 同じ時刻である
    assert loaded.starts_at.utcoffset() == datetime.timedelta(0)  # UTCとして戻る


def test_datetime_is_stored_as_utc_in_db(session: Session) -> None:
    experience = create_experience(session, create_business(session))
    create_slot(session, experience, starts_at=datetime.datetime(2026, 11, 24, 9, 0, tzinfo=JST))
    session.commit()

    raw = session.execute(text("SELECT starts_at FROM slots")).scalar_one()

    # 日本時間の9:00は、UTCの0:00
    assert str(raw).startswith("2026-11-24 00:00:00")


def test_datetime_without_timezone_is_rejected() -> None:
    column_type = UTCDateTime()

    with pytest.raises(TypeError, match="タイムゾーン"):
        column_type.process_bind_param(datetime.datetime(2026, 11, 24, 9, 0), sqlite.dialect())


def test_none_is_passed_through() -> None:
    column_type = UTCDateTime()
    dialect = sqlite.dialect()

    assert column_type.process_bind_param(None, dialect) is None
    assert column_type.process_result_value(None, dialect) is None
