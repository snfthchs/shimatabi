"""個人情報のマスク（ADR 0004）。

事業者の予約の一覧では、氏名・電話・メールを、サーバー側でマスクして返す。
フロントエンドで伏せ字にすると、レスポンスに平文が含まれてしまうため。
"""


def mask_name(name: str) -> str:
    """氏名を、先頭の1文字だけ残して伏せる。例: `山田 花子` → `山***`"""
    name = name.strip()
    if not name:
        return ""
    return f"{name[0]}***"


def mask_phone(phone: str) -> str:
    """電話番号を、先頭3桁と末尾4桁だけ残して伏せる。区切りの文字は、そのまま残す。

    例: `090-1234-5678` → `090-****-5678`
    桁数が8桁に満たないときは、末尾2桁だけ残す。
    """
    digit_count = sum(character.isdigit() for character in phone)
    if digit_count >= 8:
        keep_head, keep_tail = 3, 4
    else:
        keep_head, keep_tail = 0, 2

    masked: list[str] = []
    seen = 0
    for character in phone:
        if character.isdigit():
            seen += 1
            keep = seen <= keep_head or seen > digit_count - keep_tail
            masked.append(character if keep else "*")
        else:
            masked.append(character)
    return "".join(masked)


def mask_email(email: str) -> str:
    """メールアドレスを、先頭の1文字とドメインだけ残して伏せる。例: `h***@example.com`"""
    email = email.strip()
    local, separator, domain = email.partition("@")
    if not separator or not local:
        return "***"
    return f"{local[0]}***@{domain}"
