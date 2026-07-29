from datetime import UTC, date, datetime, timedelta

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
    EredesFetchError,
    SessionExpiredError,
    fetch_consumption,
    utc_today,
)
from portinhola.integrations.eredes_session import load_token
from portinhola.jobs.registry import job

# On the first sync we don't assume how far back the portal keeps data —
# we walk backwards a window at a time until it stops answering. Two
# consecutive empty windows end the walk (one alone could be a genuine
# gap or the portal's known flakiness); the cap is only a runaway guard.
HISTORY_WINDOW_DAYS = 31
HISTORY_EMPTY_WINDOWS_TO_STOP = 2
HISTORY_MAX_DAYS = 3650


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
    date_to = utc_today()

    try:
        if since is None:
            rows, date_from = _walk_back_history(db, app_key, supply_point.identifier, date_to)
        else:
            # Incremental: re-fetch the last stored day too, because E-Redes
            # revises recent readings (estimated -> real). Upsert dedupes.
            date_from = since.date() - timedelta(days=1)
            rows = fetch_consumption(
                db, app_key, supply_point.identifier, date_from, date_to
            )
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


def _walk_back_history(db: Session, app_key: bytes, cpe: str, date_to: date):
    """First sync: discover how far back the portal actually goes.

    Requests one window at a time, walking backwards, and stops after
    HISTORY_EMPTY_WINDOWS_TO_STOP consecutive empty windows. Returns the
    merged rows plus the oldest date actually reached, so we never have to
    guess a retention period.
    """
    merged: dict[datetime, tuple] = {}
    oldest = date_to
    empty_streak = 0
    window_end = date_to
    days_walked = 0

    while empty_streak < HISTORY_EMPTY_WINDOWS_TO_STOP and days_walked < HISTORY_MAX_DAYS:
        window_start = window_end - timedelta(days=HISTORY_WINDOW_DAYS - 1)
        try:
            rows = fetch_consumption(db, app_key, cpe, window_start, window_end)
        except EredesFetchError:
            rows = []
        if rows:
            empty_streak = 0
            for row in rows:
                merged[row[0]] = row
            oldest = window_start
        else:
            empty_streak += 1
        window_end = window_start - timedelta(days=1)
        days_walked += HISTORY_WINDOW_DAYS

    return [merged[ts] for ts in sorted(merged)], oldest


def _resolve_supply_point(db: Session) -> SupplyPoint | None:
    override = get_setting(db, "eredes_supply_point_id")
    if override:
        return db.get(SupplyPoint, int(override))
    return db.scalar(
        select(SupplyPoint)
        .where(SupplyPoint.utility == "electricity")
        .order_by(SupplyPoint.id)
    )
