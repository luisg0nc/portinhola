from sqlalchemy.orm import Session

from portinhola.core.crypto import decrypt, encrypt
from portinhola.db.settings_repo import get_setting, set_setting

TOKEN_KEY = "eredes_aat"


def save_token(db: Session, app_key: bytes, token: str) -> None:
    payload = encrypt(app_key, token.strip().encode())
    set_setting(db, TOKEN_KEY, payload.decode())


def load_token(db: Session, app_key: bytes) -> str | None:
    raw = get_setting(db, TOKEN_KEY)
    if not raw:
        return None
    try:
        token = decrypt(app_key, raw.encode()).decode()
    except Exception:  # noqa: BLE001 - corrupt/rotated key => not connected
        return None
    return token or None


def clear(db: Session) -> None:
    set_setting(db, TOKEN_KEY, "")
