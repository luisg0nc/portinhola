from portinhola.core.crypto import decrypt, encrypt
from portinhola.integrations.eredes_curl import CurlRequest
from portinhola.integrations.eredes_session import (
    clear,
    load_template,
    save_template,
    update_cookies,
)

KEY = b"k" * 32


def _req() -> CurlRequest:
    return CurlRequest(
        method="GET",
        url="https://balcaodigital.e-redes.pt/api/x?s=2026-06-01&e=2026-07-01",
        headers={"authorization": "Bearer t"},
        cookies={"PHPSESSID": "old"},
        body=None,
    )


def test_crypto_roundtrip() -> None:
    token = encrypt(KEY, b"secret")
    assert token != b"secret"
    assert decrypt(KEY, token) == b"secret"


def test_template_roundtrip(app) -> None:
    with app.state.sessionmaker() as db:
        assert load_template(db, KEY) is None
        save_template(db, KEY, _req())
    with app.state.sessionmaker() as db:
        loaded = load_template(db, KEY)
        assert loaded is not None
        assert loaded.cookies == {"PHPSESSID": "old"}
        clear(db)
        assert load_template(db, KEY) is None


def test_update_cookies_merges(app) -> None:
    with app.state.sessionmaker() as db:
        save_template(db, KEY, _req())
        update_cookies(db, KEY, {"PHPSESSID": "new99", "extra": "1"})
    with app.state.sessionmaker() as db:
        loaded = load_template(db, KEY)
        assert loaded is not None
        assert loaded.cookies == {"PHPSESSID": "new99", "extra": "1"}
