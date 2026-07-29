from sqlalchemy.orm import Session

from portinhola.core.crypto import decrypt, encrypt
from portinhola.db.settings_repo import get_setting, set_setting
from portinhola.integrations.eredes_curl import CurlRequest

CURL_KEY = "eredes_curl"


def save_template(db: Session, app_key: bytes, req: CurlRequest) -> None:
    payload = encrypt(app_key, req.model_dump_json().encode())
    set_setting(db, CURL_KEY, payload.decode())


def load_template(db: Session, app_key: bytes) -> CurlRequest | None:
    raw = get_setting(db, CURL_KEY)
    if not raw:
        return None
    try:
        return CurlRequest.model_validate_json(decrypt(app_key, raw.encode()))
    except Exception:  # noqa: BLE001 - corrupt/rotated key/old format => not connected
        return None


def update_cookies(db: Session, app_key: bytes, set_cookies: dict[str, str]) -> None:
    if not set_cookies:
        return
    template = load_template(db, app_key)
    if template is None:
        return
    merged = {**template.cookies, **set_cookies}
    save_template(db, app_key, template.model_copy(update={"cookies": merged}))


def clear(db: Session) -> None:
    set_setting(db, CURL_KEY, "")
