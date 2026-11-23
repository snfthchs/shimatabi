"""連絡先（氏名・電話・メール）の正規化と、予約の確認での照合。

予約の確認では、予約番号と、予約のときに書いた連絡先（電話またはメール）を照合する。
書き方の違い（全角、ハイフン、空白、メールの大文字小文字）で、本人が弾かれないよう、
比較の前に、書き方をそろえる。
"""

import hmac
import re
import unicodedata

# 電話番号: 数字8〜15桁。先頭に `+` を付けてよい（正規化のあとの形で確かめる）。
PHONE_PATTERN = re.compile(r"^\+?[0-9]{8,15}$")
# メールアドレス: 厳密ではなく、明らかな誤りだけを弾く（新しい依存を増やさないため）。
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_text(value: str) -> str:
    """全角・半角などの違いをそろえて（NFKC）、前後の空白を取る。"""
    return unicodedata.normalize("NFKC", value).strip()


def normalize_phone(value: str) -> str:
    """電話番号から、空白・ハイフン・括弧を取り除く。先頭の `+` は残す。"""
    return re.sub(r"[\s\-()]", "", normalize_text(value))


def normalize_email(value: str) -> str:
    """メールアドレスを、小文字にそろえる。"""
    return normalize_text(value).lower()


def normalize_booking_number(value: str) -> str:
    """予約番号を、大文字にそろえる。"""
    return normalize_text(value).upper()


def contact_matches(contact: str, *, phone: str, email: str) -> bool:
    """入力された連絡先が、予約の電話番号またはメールと一致するかを確かめる。

    `@` を含めばメール、含まなければ電話番号として比べる。比較は、時間の差から値を
    推測されにくいよう、定数時間で行う。
    """
    normalized = normalize_text(contact)
    if "@" in normalized:
        given, stored = normalize_email(normalized), normalize_email(email)
    else:
        given, stored = normalize_phone(normalized), normalize_phone(phone)
    if not given:
        return False
    return hmac.compare_digest(given.encode("utf-8"), stored.encode("utf-8"))
