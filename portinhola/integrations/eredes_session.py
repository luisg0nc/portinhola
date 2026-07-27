import json

from sqlalchemy.orm import Session

from portinhola.core.crypto import decrypt, encrypt
from portinhola.db.settings_repo import get_setting, set_setting

COOKIES_KEY = "eredes_cookies"


def save_cookies(db: Session, app_key: bytes, cookies: list[dict]) -> None:
    payload = encrypt(app_key, json.dumps(cookies).encode())
    set_setting(db, COOKIES_KEY, payload.decode())


def load_cookies(db: Session, app_key: bytes) -> list[dict] | None:
    raw = get_setting(db, COOKIES_KEY)
    if not raw:
        return None
    try:
        return json.loads(decrypt(app_key, raw.encode()))
    except Exception:  # noqa: BLE001 - corrupted/rotated key means no session
        return None


def clear(db: Session) -> None:
    set_setting(db, COOKIES_KEY, "")
