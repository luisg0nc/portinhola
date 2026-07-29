from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.config import Config
from portinhola.core.alerts import raise_alert
from portinhola.core.notify import send as notify_send
from portinhola.core.secrets import load_or_create_app_key
from portinhola.db.consumption_repo import last_ts, upsert_intervals
from portinhola.db.models import SupplyPoint
from portinhola.db.settings_repo import get_setting, set_setting
from portinhola.integrations.eredes_api import (
    SessionExpiredError,
    fetch_consumption,
    utc_today,
)
from portinhola.integrations.eredes_session import load_token
from portinhola.jobs.registry import job

HISTORY_BACKFILL_DAYS = 365


@job("eredes_sync")
def eredes_sync(db: Session) -> str:
    app_key = load_or_create_app_key(Config().data_dir)
    if load_token(db, app_key) is None:
        raise_alert(
            db,
            "eredes_not_connected",
            "E-Redes is not connected — import your session token in Settings.",
            dedup_key="eredes_not_connected",
        )
        return "not connected; skipped"

    supply_point = _resolve_supply_point(db)
    if supply_point is None:
        return "no electricity supply point; skipped"

    since = last_ts(db, supply_point.id)
    date_from = (
        since.date() - timedelta(days=1)
        if since is not None
        else utc_today() - timedelta(days=HISTORY_BACKFILL_DAYS)
    )
    date_to = utc_today()

    try:
        rows = fetch_consumption(db, app_key, supply_point.identifier, date_from, date_to)
    except SessionExpiredError:
        raise_alert(
            db,
            "eredes_session_expired",
            "E-Redes session expired — reconnect in Settings.",
            dedup_key="eredes_session_expired",
        )
        notify_send(db, "Portinhola", "E-Redes session expired — tap to reconnect.")
        raise

    inserted, updated = upsert_intervals(
        db,
        supply_point.id,
        [(ts, kwh, "eredes_scrape", quality) for ts, kwh, quality in rows],
    )
    set_setting(db, "eredes_last_sync", datetime.now(UTC).isoformat())
    return f"{len(rows)} intervals ({inserted} new, {updated} updated) from {date_from} to {date_to}"


def _resolve_supply_point(db: Session) -> SupplyPoint | None:
    override = get_setting(db, "eredes_supply_point_id")
    if override:
        return db.get(SupplyPoint, int(override))
    return db.scalar(
        select(SupplyPoint)
        .where(SupplyPoint.utility == "electricity")
        .order_by(SupplyPoint.id)
    )
