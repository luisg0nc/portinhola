import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from portinhola.api.deps import SESSION_COOKIE, get_db, require_auth
from portinhola.core.security import session_age
from portinhola.db.settings_repo import get_setting
from portinhola.integrations import eredes_login, eredes_session

router = APIRouter()


@router.get("/status", dependencies=[Depends(require_auth)])
def status(db: Session = Depends(get_db)) -> dict:
    connected = bool(get_setting(db, eredes_session.COOKIES_KEY))
    return {"connected": connected, "last_sync": get_setting(db, "eredes_last_sync")}


@router.post("/disconnect", status_code=204, dependencies=[Depends(require_auth)])
def disconnect(db: Session = Depends(get_db)) -> None:
    eredes_session.clear(db)


@router.websocket("/login")
async def login_ws(websocket: WebSocket) -> None:
    app = websocket.app
    token = websocket.cookies.get(SESSION_COOKIE)
    age = session_age(app.state.app_key, token) if token else None
    if age is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()

    async def on_success(cookies: list[dict]) -> None:
        with app.state.sessionmaker() as db:
            eredes_session.save_cookies(db, app.state.app_key, cookies)

    try:
        await eredes_login.run_login_session(websocket, on_success)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - surface any browser crash to the client
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:  # noqa: BLE001, S110 - socket may already be gone
            pass
    finally:
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001, S110 - already closed is fine
            pass
