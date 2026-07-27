from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.db.settings_repo import get_setting, set_setting

router = APIRouter(dependencies=[Depends(require_auth)])


class SettingsBody(BaseModel):
    language: Literal["pt", "en"]


@router.get("")
def read_settings(db: Session = Depends(get_db)) -> dict[str, str]:
    return {"language": get_setting(db, "language") or "pt"}


@router.put("", status_code=204)
def update_settings(body: SettingsBody, db: Session = Depends(get_db)) -> None:
    set_setting(db, "language", body.language)
