from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.db.models import Alert

router = APIRouter(dependencies=[Depends(require_auth)])


class AlertOut(BaseModel):
    id: int
    type: str
    message: str
    created_at: datetime
    read: bool

    model_config = {"from_attributes": True}


@router.get("")
def list_alerts(unread: bool = False, db: Session = Depends(get_db)) -> list[AlertOut]:
    query = select(Alert).order_by(Alert.created_at.desc())
    if unread:
        query = query.where(Alert.read.is_(False))
    return [AlertOut.model_validate(row) for row in db.scalars(query)]


@router.post("/{alert_id}/read", status_code=204)
def mark_read(alert_id: int, db: Session = Depends(get_db)) -> None:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert_not_found")
    alert.read = True
    db.commit()
