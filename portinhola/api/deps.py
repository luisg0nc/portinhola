from collections.abc import Iterator

from fastapi import HTTPException, Request, Response
from sqlalchemy.orm import Session

from portinhola.core.security import create_session_token, session_age

SESSION_COOKIE = "portinhola_session"
SESSION_MAX_AGE = 30 * 86400
SESSION_REFRESH_AFTER = 86400


def get_db(request: Request) -> Iterator[Session]:
    db = request.app.state.sessionmaker()
    try:
        yield db
    finally:
        db.close()


def set_session_cookie(response: Response, request: Request) -> None:
    token = create_session_token(request.app.state.app_key)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.app.state.config.cookie_secure,
    )


def require_auth(request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    age = session_age(request.app.state.app_key, token) if token else None
    if age is None or age > SESSION_MAX_AGE:
        raise HTTPException(status_code=401, detail="not_authenticated")
    if age > SESSION_REFRESH_AFTER:
        set_session_cookie(response, request)
