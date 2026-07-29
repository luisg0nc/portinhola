from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.db.settings_repo import get_setting
from portinhola.integrations import eredes_session
from portinhola.integrations.eredes_curl import (
    CurlValidationError,
    parse_curl,
    read_expiry,
    validate,
)

router = APIRouter(dependencies=[Depends(require_auth)])


class ImportBody(BaseModel):
    curl: str


@router.get("/status")
def status(request: Request, db: Session = Depends(get_db)) -> dict:
    template = eredes_session.load_template(db, request.app.state.app_key)
    valid_until = None
    if template is not None:
        expiry = read_expiry(template)
        valid_until = expiry.isoformat() if expiry else None
    return {
        "connected": template is not None,
        "last_sync": get_setting(db, "eredes_last_sync"),
        "valid_until": valid_until,
    }


@router.post("/import")
def import_curl(body: ImportBody, request: Request, db: Session = Depends(get_db)) -> dict:
    try:
        req = parse_curl(body.curl)
        validate(req)
    except CurlValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from exc
    eredes_session.save_template(db, request.app.state.app_key, req)
    expiry = read_expiry(req)
    return {"valid_until": expiry.isoformat() if expiry else None}


@router.post("/disconnect", status_code=204)
def disconnect(db: Session = Depends(get_db)) -> None:
    eredes_session.clear(db)
