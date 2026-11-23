"""AIに渡す前の、個人情報らしき文字列の検知と、伏せ字への置き換えのテスト。

使う値は、すべて架空のもの（電話番号は 090-1234-5678 のような例、メールは example.com）。
"""

import pytest

from app.ai.pii_guard import MaskResult, mask_personal_info


@pytest.mark.parametrize(
    ("message", "expected", "kind"),
    [
        ("090-1234-5678に電話して", "[電話番号]に電話して", "電話番号"),
        ("０９０－１２３４－５６７８です", "[電話番号]です", "電話番号"),  # 全角
        ("09012345678", "[電話番号]", "電話番号"),
        ("03 1234 5678", "[電話番号]", "電話番号"),
        ("098-123-4567", "[電話番号]", "電話番号"),
        ("0120-123-456", "[電話番号]", "電話番号"),
        ("+81 90 1234 5678", "[電話番号]", "電話番号"),
        # 市外局番を括弧で囲む書き方、ドット区切り、国番号のあとの（0）
        ("(03)1234-5678", "[電話番号]", "電話番号"),
        ("03(1234)5678", "[電話番号]", "電話番号"),
        ("０３（１２３４）５６７８", "[電話番号]", "電話番号"),
        ("(090)1234-5678に電話して", "[電話番号]に電話して", "電話番号"),
        ("090.1234.5678", "[電話番号]", "電話番号"),
        ("+81(0)90-1234-5678", "[電話番号]", "電話番号"),
        ("+81-90-1234-5678", "[電話番号]", "電話番号"),
        ("taro.yamada+test@example.com まで", "[メールアドレス] まで", "メールアドレス"),
        ("TARO@Example.CO.JP", "[メールアドレス]", "メールアドレス"),
        ("〒900-0001 那覇市", "[郵便番号] 那覇市", "郵便番号"),
        ("900-0001", "[郵便番号]", "郵便番号"),
        ("4111 1111 1111 1111", "[カード番号]", "カード番号"),
        ("4111-1111-1111-1111", "[カード番号]", "カード番号"),
        # 検査の数字が合わなくても、一部が残らないように、すべて伏せる
        ("4111 1111 1111 1112", "[カード番号]", "カード番号"),
        ("1234 5678 9012", "[番号]", "番号"),
    ],
)
def test_personal_info_is_replaced_with_a_label(message: str, expected: str, kind: str) -> None:
    result = mask_personal_info(message)

    assert result.text == expected
    assert result.kinds == (kind,)
    assert result.masked is True


@pytest.mark.parametrize(
    "message",
    [
        "明日の午後、子連れ4人で海の体験がしたい",
        "2026-11-24の午後、3人で",
        "11/30 2人 那覇から60分以内",
        "11月30日の10時から",
        "予約番号は不要です",
        "大人2人と子供1人で、1時間以内",
        # 郵便番号の形に見えるが、直後が単位（金額・人数・時間）のもの
        "予算は500-1000円くらい",
        "予算は500-1000 円くらい",
        "300-1000人くらいの団体",
        "(03)で始まる番号以外で、予算は1000円",
        "",
    ],
)
def test_ordinary_requests_are_left_unchanged(message: str) -> None:
    result = mask_personal_info(message)

    assert result.text == message
    assert result.kinds == ()
    assert result.masked is False


def test_several_kinds_in_one_message_are_all_masked() -> None:
    message = "明日の午後、090-1234-5678か taro@example.com に連絡ください。〒900-0001"

    result = mask_personal_info(message)

    assert result.text == "明日の午後、[電話番号]か [メールアドレス] に連絡ください。[郵便番号]"
    # 種類は、検知した順（メール、カード、電話、郵便、番号）に並ぶ
    assert result.kinds == ("メールアドレス", "電話番号", "郵便番号")


def test_the_same_kind_is_reported_once() -> None:
    result = mask_personal_info("090-1234-5678 と 080-9999-0000")

    assert result.text == "[電話番号] と [電話番号]"
    assert result.kinds == ("電話番号",)


def test_the_result_never_contains_the_original_values() -> None:
    message = "090-1234-5678 taro@example.com 〒900-0001 4111 1111 1111 1111 1234 5678 9012"

    result = mask_personal_info(message)

    for secret in ("090", "1234", "taro", "example.com", "900-0001", "4111", "5678", "9012"):
        assert secret not in result.text


def test_a_result_without_kinds_is_not_masked() -> None:
    assert MaskResult(text="x").masked is False


def test_a_postal_code_without_the_mark_is_still_masked_when_no_unit_follows() -> None:
    result = mask_personal_info("宿は900-0001です")

    assert result.text == "宿は[郵便番号]です"
    assert result.kinds == ("郵便番号",)
