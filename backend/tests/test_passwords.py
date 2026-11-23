from app.passwords import hash_password, verify_password, verify_password_against_dummy


def test_hash_is_argon2id_and_differs_each_time() -> None:
    first = hash_password("correct-horse-battery")
    second = hash_password("correct-horse-battery")

    assert first.startswith("$argon2id$")
    assert first != second  # ソルト（毎回違う値）が入る
    assert "correct-horse-battery" not in first


def test_verify_accepts_the_right_password() -> None:
    assert verify_password(hash_password("correct-horse-battery"), "correct-horse-battery")


def test_verify_rejects_a_wrong_password() -> None:
    assert not verify_password(hash_password("correct-horse-battery"), "wrong-password")


def test_verify_treats_a_broken_hash_as_a_mismatch() -> None:
    assert not verify_password("this-is-not-a-hash", "anything")
    assert not verify_password("", "anything")


def test_dummy_verification_does_not_raise() -> None:
    verify_password_against_dummy("anything")  # 例外が出ないこと。戻り値は使わない
