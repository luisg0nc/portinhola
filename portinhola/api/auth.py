import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from portinhola.api.deps import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    get_db,
    require_auth,
    set_session_cookie,
)
from portinhola.core.security import hash_password, session_age, verify_password
from portinhola.db.settings_repo import get_setting, set_setting

router = APIRouter()

RATE_WINDOW = 900
RATE_LIMIT = 5
MIN_PASSWORD_LENGTH = 8
_failed_logins: dict[str, list[float]] = {}


class PasswordBody(BaseModel):
    password: str


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


def _rate_limited(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _failed_logins.get(ip, []) if now - t < RATE_WINDOW]
    _failed_logins[ip] = hits
    return len(hits) >= RATE_LIMIT


@router.get("/status")
def auth_status(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    token = request.cookies.get(SESSION_COOKIE)
    age = session_age(request.app.state.app_key, token) if token else None
    return {
        "setup_required": get_setting(db, "password_hash") is None,
        "authenticated": age is not None and age <= SESSION_MAX_AGE,
    }


@router.post("/setup", status_code=204)
def setup(
    body: PasswordBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    if get_setting(db, "password_hash") is not None:
        raise HTTPException(status_code=409, detail="already_configured")
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=422, detail="password_too_short")
    set_setting(db, "password_hash", hash_password(body.password))
    set_session_cookie(response, request)


@router.post("/login", status_code=204)
def login(
    body: PasswordBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip):
        raise HTTPException(status_code=429, detail="too_many_attempts")
    stored = get_setting(db, "password_hash")
    if stored is None or not verify_password(stored, body.password):
        _failed_logins.setdefault(ip, []).append(time.time())
        raise HTTPException(status_code=401, detail="invalid_password")
    set_session_cookie(response, request)


@router.post("/logout", status_code=204, dependencies=[Depends(require_auth)])
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


@router.post("/change-password", status_code=204, dependencies=[Depends(require_auth)])
def change_password(body: ChangePasswordBody, db: Session = Depends(get_db)) -> None:
    stored = get_setting(db, "password_hash")
    if stored is None or not verify_password(stored, body.current_password):
        raise HTTPException(status_code=401, detail="invalid_password")
    if len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=422, detail="password_too_short")
    set_setting(db, "password_hash", hash_password(body.new_password))
