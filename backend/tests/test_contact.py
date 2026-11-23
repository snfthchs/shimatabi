import pytest

from app.contact import (
    EMAIL_PATTERN,
    PHONE_PATTERN,
    contact_matches,
    normalize_booking_number,
    normalize_email,
    normalize_phone,
)

PHONE = "09012345678"
EMAIL = "hanako@example.com"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("090-1234-5678", "09012345678"),
        ("０９０－１２３４－５６７８", "09012345678"),  # 全角
        ("090 1234 5678", "09012345678"),
        ("(090) 1234-5678", "09012345678"),
        ("+81 90-1234-5678", "+819012345678"),
    ],
)
def test_normalize_phone(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


def test_normalize_email_lowercases_and_strips() -> None:
    assert normalize_email("  Hanako@Example.COM ") == "hanako@example.com"


def test_normalize_booking_number_uppercases() -> None:
    assert normalize_booking_number(" abcd234567 ") == "ABCD234567"


@pytest.mark.parametrize("phone", ["09012345678", "+819012345678", "0312345678"])
def test_phone_pattern_accepts_valid_numbers(phone: str) -> None:
    assert PHONE_PATTERN.match(phone)


@pytest.mark.parametrize("phone", ["", "123", "abcdefghij", "0901234567890123456", "090-1234-5678"])
def test_phone_pattern_rejects_invalid_numbers(phone: str) -> None:
    assert not PHONE_PATTERN.match(phone)  # ハイフンは、正規化のあとの形で確かめる


@pytest.mark.parametrize("email", ["a@example.com", "t.sato+x@example.co.jp"])
def test_email_pattern_accepts_valid_addresses(email: str) -> None:
    assert EMAIL_PATTERN.match(email)


@pytest.mark.parametrize("email", ["", "no-at-sign", "a@b", "a b@example.com", "@example.com"])
def test_email_pattern_rejects_invalid_addresses(email: str) -> None:
    assert not EMAIL_PATTERN.match(email)


@pytest.mark.parametrize(
    "contact",
    ["09012345678", "090-1234-5678", "０９０－１２３４－５６７８", " 090 1234 5678 "],
)
def test_phone_in_any_writing_matches(contact: str) -> None:
    assert contact_matches(contact, phone=PHONE, email=EMAIL)


@pytest.mark.parametrize(
    "contact", ["hanako@example.com", "HANAKO@Example.com", " hanako@example.com "]
)
def test_email_in_any_case_matches(contact: str) -> None:
    assert contact_matches(contact, phone=PHONE, email=EMAIL)


@pytest.mark.parametrize(
    "contact",
    ["09012345679", "other@example.com", "", "   ", "hanako", "090-1234"],
)
def test_other_contacts_do_not_match(contact: str) -> None:
    assert not contact_matches(contact, phone=PHONE, email=EMAIL)


def test_a_phone_number_does_not_match_the_email_and_vice_versa() -> None:
    # 電話番号の欄に、メールアドレスを書いても、電話番号とは比べない（種類が違う）
    assert not contact_matches(EMAIL, phone=EMAIL, email=PHONE)
