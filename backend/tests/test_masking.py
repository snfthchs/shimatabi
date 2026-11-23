import pytest

from app.masking import mask_email, mask_name, mask_phone


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("山田 花子", "山***"),
        ("  佐藤 次郎  ", "佐***"),
        ("A", "A***"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_mask_name(name: str, expected: str) -> None:
    assert mask_name(name) == expected


@pytest.mark.parametrize(
    ("phone", "expected"),
    [
        ("090-1234-5678", "090-****-5678"),
        ("09012345678", "090****5678"),
        ("+81 90 1234 5678", "+81 9* **** 5678"),  # 先頭3桁（8・1・9）と、末尾4桁を残す
        ("1234567", "*****67"),  # 8桁に満たないときは、末尾2桁だけ残す
        ("", ""),
    ],
)
def test_mask_phone(phone: str, expected: str) -> None:
    assert mask_phone(phone) == expected


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("hanako@example.com", "h***@example.com"),
        ("  t.sato@example.co.jp ", "t***@example.co.jp"),
        ("no-at-sign", "***"),
        ("@example.com", "***"),
        ("", "***"),
    ],
)
def test_mask_email(email: str, expected: str) -> None:
    assert mask_email(email) == expected


def test_masked_values_do_not_contain_the_original() -> None:
    assert "1234" not in mask_phone("090-1234-5678")
    assert "hanako" not in mask_email("hanako@example.com")
    assert "花子" not in mask_name("山田 花子")
