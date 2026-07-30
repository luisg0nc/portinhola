from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.core.scheduler import spawn_job
from portinhola.db.models import Job, SupplyPoint
from portinhola.db.settings_repo import get_setting
from portinhola.integrations import eredes_session

router = APIRouter(dependencies=[Depends(require_auth)])


class ImportBody(BaseModel):
    token: str


@router.get("/status")
def status(request: Request, db: Session = Depends(get_db)) -> dict:
    token = eredes_session.load_token(db, request.app.state.app_key)
    has_sp = (
        db.scalar(select(SupplyPoint.id).where(SupplyPoint.utility == "electricity").limit(1))
        is not None
    )
    last_job_row = db.scalar(
        select(Job).where(Job.type == "eredes_sync").order_by(Job.id.desc()).limit(1)
    )
    last_job = None
    if last_job_row is not None:
        last_job = {
            "status": last_job_row.status,
            "message": (
                last_job_row.error if last_job_row.status == "failed" else last_job_row.log
            ),
            "finished_at": (
                last_job_row.finished_at.isoformat() if last_job_row.finished_at else None
            ),
        }
    return {
        "connected": token is not None,
        "last_sync": get_setting(db, "eredes_last_sync"),
        "needs_supply_point": not has_sp,
        "last_job": last_job,
    }


@router.post("/import")
def import_token(body: ImportBody, request: Request, db: Session = Depends(get_db)) -> dict:
    token = body.token.strip()
    if not token or "=" in token or len(token) < 8:
        raise HTTPException(status_code=422, detail="invalid_token")
    eredes_session.save_token(db, request.app.state.app_key, token)
    # The token is short-lived (~91 min) and cannot be renewed server-side,
    # so sync straight away while it is certainly valid.
    spawn_job("eredes_sync")
    return {"connected": True, "sync_started": True}


@router.post("/disconnect", status_code=204)
def disconnect(db: Session = Depends(get_db)) -> None:
    eredes_session.clear(db)
