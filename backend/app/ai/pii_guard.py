"""AIに渡す前の、個人情報らしき文字列の検知と、伏せ字への置き換え。

旅行者がAIコンシェルジュに書いた文章に、誤って個人情報が入っていても、外部のAIサービスへ
送らないようにする（`docs/adr/0007-llm-provider.md`）。AIプロバイダーの種類（モック・LLM）に
かかわらず、`app.services.concierge.run_concierge` が、AIを呼ぶ前に通す。

検知するのは、**形が決まっているもの**だけである。

| 種類 | 例 |
|---|---|
| メールアドレス | `taro@example.com` |
| カード番号 | 13〜19桁の数字の並び（空白・ハイフン区切りを含む） |
| 電話番号 | `090-1234-5678`、`03 1234 5678`、`+81 90 1234 5678` |
| 郵便番号 | `〒900-0001`、`900-0001` |
| 12桁の番号 | `1234 5678 9012`（マイナンバーなど） |

**氏名や住所は、形が決まっていないので、確実には検知できない。** 画面の注意書き（個人情報は
入力しないでください）と、ログに残さない作りで補う。残るリスクは、ADR 0007 に書いてある。

入力した値は、個人情報を含みうるので、戻り値以外には出さない（ログにも、例外にも含めない）。
"""

import re
import unicodedata
from dataclasses import dataclass

# ハイフンの仲間（NFKCでは、`ー`（長音）と `−`（マイナス記号）が、そのまま残る）
_HYPHEN = r"[-‐‑‒–—―−ー]"

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
_CARD = re.compile(r"(?<![\d])(?:\d[ \-]?){12,18}\d(?![\d])")
_SEP = rf"(?:{_HYPHEN}|[ ])?"
_PHONE = re.compile(rf"(?<![\d])(?:\+81[ \-]?)?0?\d{{1,4}}{_SEP}\d{{1,4}}{_SEP}\d{{3,4}}(?![\d])")
_POSTAL = re.compile(rf"(?:〒\s*)?(?<![\d])\d{{3}}{_HYPHEN}\d{{4}}(?![\d])")
_TWELVE = re.compile(r"(?<![\d])\d{4}[ \-]?\d{4}[ \-]?\d{4}(?![\d])")

EMAIL_LABEL = "メールアドレス"
CARD_LABEL = "カード番号"
PHONE_LABEL = "電話番号"
POSTAL_LABEL = "郵便番号"
TWELVE_LABEL = "番号"


@dataclass(frozen=True)
class MaskResult:
    """伏せ字にしたあとの文章と、見つけた個人情報の種類（なければ空）。"""

    text: str
    kinds: tuple[str, ...] = ()

    @property
    def masked(self) -> bool:
        return bool(self.kinds)


def _is_phone(candidate: str) -> bool:
    """電話番号らしいか。数字だけにして、桁数と、先頭の数字で判断する。"""
    digits = re.sub(r"\D", "", candidate)
    if candidate.lstrip().startswith("+81"):
        digits = "0" + digits[2:]  # 国番号の81を、国内の先頭の0に直す
    if not digits.startswith("0"):
        return False
    # 固定電話・携帯電話は10〜11桁。
    return len(digits) in (10, 11)


def mask_personal_info(message: str) -> MaskResult:
    """文章の中の、個人情報らしき文字列を、`[電話番号]` のような印に置き換える。

    全角の数字や記号は、半角にそろえてから調べる（置き換えたときは、そろえたあとの文章を返す。
    何も見つからなければ、元の文章を、そのまま返す）。
    """
    text = unicodedata.normalize("NFKC", message)
    kinds: list[str] = []

    def record(label: str) -> None:
        if label not in kinds:
            kinds.append(label)

    def replace_email(match: re.Match[str]) -> str:
        record(EMAIL_LABEL)
        return f"[{EMAIL_LABEL}]"

    def replace_card(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group())
        # 旅行の相談に、13桁以上の数字の並びが出ることは、ほぼない。検査の数字（Luhn）が合わない
        # ものも、一部が残らないように、すべて伏せる。
        if 13 <= len(digits) <= 19:
            record(CARD_LABEL)
            return f"[{CARD_LABEL}]"
        return match.group()

    def replace_phone(match: re.Match[str]) -> str:
        if _is_phone(match.group()):
            record(PHONE_LABEL)
            return f"[{PHONE_LABEL}]"
        return match.group()

    def replace_postal(match: re.Match[str]) -> str:
        record(POSTAL_LABEL)
        return f"[{POSTAL_LABEL}]"

    def replace_twelve(match: re.Match[str]) -> str:
        record(TWELVE_LABEL)
        return f"[{TWELVE_LABEL}]"

    # 長くて、特徴の強いものから順に置き換える（先に置き換えたものは、印になり、あとで一致しない）。
    text = _EMAIL.sub(replace_email, text)
    text = _CARD.sub(replace_card, text)
    text = _PHONE.sub(replace_phone, text)
    text = _POSTAL.sub(replace_postal, text)
    text = _TWELVE.sub(replace_twelve, text)
    if not kinds:
        return MaskResult(text=message)  # 何も見つからなければ、元の文章を、そのまま返す
    return MaskResult(text=text, kinds=tuple(kinds))
