from portinhola.core.security import (
    create_session_token,
    hash_password,
    session_age,
    verify_password,
)

KEY = b"k" * 32
OTHER_KEY = b"x" * 32


def test_password_roundtrip() -> None:
    h = hash_password("correct horse")
    assert verify_password(h, "correct horse")
    assert not verify_password(h, "wrong")


def test_hash_is_not_plaintext() -> None:
    assert "correct horse" not in hash_password("correct horse")


def test_fresh_token_has_small_age() -> None:
    token = create_session_token(KEY)
    age = session_age(KEY, token)
    assert age is not None
    assert 0 <= age < 10


def test_forged_or_foreign_token_is_invalid() -> None:
    token = create_session_token(KEY)
    assert session_age(OTHER_KEY, token) is None
    assert session_age(KEY, "garbage") is None
