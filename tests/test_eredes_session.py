from portinhola.core.crypto import decrypt, encrypt
from portinhola.integrations.eredes_session import clear, load_token, save_token

KEY = b"k" * 32


def test_crypto_roundtrip() -> None:
    token = encrypt(KEY, b"secret")
    assert token != b"secret"
    assert decrypt(KEY, token) == b"secret"


def test_token_roundtrip(app) -> None:
    with app.state.sessionmaker() as db:
        assert load_token(db, KEY) is None
        save_token(db, KEY, "  aat-value-123  ")
    with app.state.sessionmaker() as db:
        assert load_token(db, KEY) == "aat-value-123"  # trimmed
        clear(db)
        assert load_token(db, KEY) is None
