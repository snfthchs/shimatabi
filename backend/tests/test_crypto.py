import pytest
from cryptography.fernet import Fernet
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.crypto import ConfigurationError, DecryptionError, get_cipher
from app.db import make_session_factory
from app.models import Booking
from tests.factories import create_booking, create_business, create_experience, create_slot

NAME = "山田 花子"
PHONE = "090-1234-5678"
EMAIL = "hanako@example.com"


def _new_key() -> str:
    return Fernet.generate_key().decode()


def _create_booking(session: Session, **overrides: str) -> Booking:
    experience = create_experience(session, create_business(session))
    slot = create_slot(session, experience)
    return create_booking(
        session, slot, guest_name=NAME, guest_phone=PHONE, guest_email=EMAIL, **overrides
    )


def test_personal_info_is_encrypted_in_db(session: Session) -> None:
    _create_booking(session)
    session.commit()

    # 暗号化されていることを確かめるため、このテストの中だけ、生のSQLで保存された値を読む。
    row = session.execute(text("SELECT guest_name, guest_phone, guest_email FROM bookings")).one()

    for raw, plain in zip(row, (NAME, PHONE, EMAIL), strict=True):
        assert raw != plain
        assert plain not in raw
    assert "example.com" not in row[2]


def test_personal_info_is_decrypted_when_read(session: Session) -> None:
    booking = _create_booking(session)
    session.commit()

    session.expire_all()  # 保持している値を捨てて、DBから読み直す
    loaded = session.get(Booking, booking.id)

    assert loaded is not None
    assert (loaded.guest_name, loaded.guest_phone, loaded.guest_email) == (NAME, PHONE, EMAIL)


def test_same_value_is_encrypted_differently_each_time(session: Session) -> None:
    experience = create_experience(session, create_business(session))
    slot = create_slot(session, experience)
    create_booking(session, slot, booking_number="TESTA23456", guest_name=NAME)
    create_booking(session, slot, booking_number="TESTB23456", guest_name=NAME)
    session.commit()

    names = session.execute(text("SELECT guest_name FROM bookings")).scalars().all()

    assert len(set(names)) == 2


def test_missing_key_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PII_ENCRYPTION_KEY")

    with pytest.raises(ConfigurationError, match="PII_ENCRYPTION_KEY"):
        get_cipher()


def test_blank_key_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PII_ENCRYPTION_KEY", " , ")

    with pytest.raises(ConfigurationError, match="空"):
        get_cipher()


def test_invalid_key_raises_error_without_leaking_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PII_ENCRYPTION_KEY", "not-a-valid-key")

    with pytest.raises(ConfigurationError, match="形式") as error:
        get_cipher()

    assert "not-a-valid-key" not in str(error.value)


def test_data_cannot_be_decrypted_with_another_key(
    engine: Engine, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    booking = _create_booking(session)
    session.commit()

    monkeypatch.setenv("PII_ENCRYPTION_KEY", _new_key())
    with make_session_factory(engine)() as another_session:
        with pytest.raises(DecryptionError) as error:
            another_session.get(Booking, booking.id)

    # エラーのメッセージに、個人情報を含めない
    for personal_info in (NAME, PHONE, EMAIL):
        assert personal_info not in str(error.value)


def test_old_keys_can_still_decrypt_after_rotation(
    engine: Engine, session: Session, pii_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_booking = _create_booking(session)
    session.commit()

    # 新しい鍵を先頭に足す。先頭の鍵で暗号化し、すべての鍵で復号を試す。
    new_key = _new_key()
    monkeypatch.setenv("PII_ENCRYPTION_KEY", f"{new_key},{pii_key}")
    with make_session_factory(engine)() as rotated_session:
        loaded = rotated_session.get(Booking, old_booking.id)
        assert loaded is not None
        assert loaded.guest_name == NAME  # 旧い鍵で暗号化したものも読める

        slot = create_slot(
            rotated_session,
            create_experience(rotated_session, create_business(rotated_session, "別の事業者")),
        )
        new_booking = create_booking(rotated_session, slot, booking_number="TESTB23456")
        rotated_session.commit()
        new_booking_id = new_booking.id

    # 旧い鍵だけでは、新しい鍵で暗号化したものは読めない（先頭の鍵で暗号化されている）
    monkeypatch.setenv("PII_ENCRYPTION_KEY", pii_key)
    with make_session_factory(engine)() as old_key_session:
        with pytest.raises(DecryptionError):
            old_key_session.get(Booking, new_booking_id)
