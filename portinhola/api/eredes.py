from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.db.settings_repo import get_setting
from portinhola.integrations import eredes_session

router = APIRouter(dependencies=[Depends(require_auth)])


class ImportBody(BaseModel):
    token: str


@router.get("/status")
def status(request: Request, db: Session = Depends(get_db)) -> dict:
    token = eredes_session.load_token(db, request.app.state.app_key)
    return {
        "connected": token is not None,
        "last_sync": get_setting(db, "eredes_last_sync"),
    }


@router.post("/import")
def import_token(body: ImportBody, request: Request, db: Session = Depends(get_db)) -> dict:
    token = body.token.strip()
    if not token or "=" in token or len(token) < 8:
        raise HTTPException(status_code=422, detail="invalid_token")
    eredes_session.save_token(db, request.app.state.app_key, token)
    return {"connected": True}


@router.post("/disconnect", status_code=204)
def disconnect(db: Session = Depends(get_db)) -> None:
    eredes_session.clear(db)
