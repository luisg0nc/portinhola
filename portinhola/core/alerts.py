from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.db.models import Alert


def raise_alert(
    db: Session, type_: str, message: str, dedup_key: str | None = None
) -> tuple[Alert, bool]:
    """Insert (or refresh, when dedup_key matches) an alert.

    Returns (alert, created) — created is False when an existing deduped
    alert was refreshed instead of inserted.
    """
    if dedup_key is not None:
        existing = db.scalar(select(Alert).where(Alert.dedup_key == dedup_key))
        if existing is not None:
            existing.message = message
            existing.created_at = datetime.now(UTC)
            existing.read = False
            db.commit()
            return existing, False
    alert = Alert(type=type_, message=message, created_at=datetime.now(UTC), dedup_key=dedup_key)
    db.add(alert)
    db.commit()
    return alert, True
