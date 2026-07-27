from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.core import notify
from portinhola.db.settings_repo import get_setting, set_setting

router = APIRouter(dependencies=[Depends(require_auth)])


class SettingsBody(BaseModel):
    language: Literal["pt", "en"]
    apprise_urls: str | None = None
    eredes_sync_time: str | None = None


@router.get("")
def read_settings(db: Session = Depends(get_db)) -> dict[str, str]:
    return {
        "language": get_setting(db, "language") or "pt",
        "apprise_urls": get_setting(db, "apprise_urls") or "",
        "eredes_sync_time": get_setting(db, "eredes_sync_time") or "07:00",
    }


@router.put("", status_code=204)
def update_settings(body: SettingsBody, db: Session = Depends(get_db)) -> None:
    set_setting(db, "language", body.language)
    if body.apprise_urls is not None:
        set_setting(db, "apprise_urls", body.apprise_urls)
    if body.eredes_sync_time is not None:
        set_setting(db, "eredes_sync_time", body.eredes_sync_time)


@router.post("/test-notification")
def test_notification(db: Session = Depends(get_db)) -> dict[str, bool]:
    return {"sent": notify.send(db, "Portinhola", "Test notification")}
