from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.config import Config
from portinhola.core.alerts import raise_alert
from portinhola.core.notify import send as notify_send
from portinhola.core.secrets import load_or_create_app_key
from portinhola.db.consumption_repo import first_ts, last_ts, upsert_intervals
from portinhola.db.models import SupplyPoint
from portinhola.db.settings_repo import get_setting, set_setting
from portinhola.integrations.eredes_api import (
    EredesFetchError,
    SessionExpiredError,
    fetch_consumption,
    utc_today,
)
from portinhola.integrations.eredes_session import load_token
from portinhola.jobs.registry import JobFailure, job

# The portal rejects or times out on wide ranges, and with `wait: true`
# even a 31-day window can take a while to compute server-side. Every
# window is therefore fetched AND persisted individually: if the token
# expires or the job watchdog kills the process mid-backfill, everything
# already fetched survives and the next sync resumes from the newest
# stored interval.
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
        raise JobFailure("not_connected")

    supply_point = _resolve_supply_point(db)
    if supply_point is None:
        # Without a supply point we don't know which CPE to query, so this
        # must fail loudly — a silent "skipped" success reads as a sync.
        raise_alert(
            db,
            "eredes_no_supply_point",
            "E-Redes sync needs an electricity supply point (CPE) — "
            "add one in Settings or upload a bill first.",
            dedup_key="eredes_no_supply_point",
        )
        raise JobFailure("no_supply_point")

    since = last_ts(db, supply_point.id)
    date_to = utc_today()
    backfill_done = get_setting(db, "eredes_backfill_done") == "1"

    try:
        if since is None:
            total, inserted, updated, date_from = _walk_back_history(
                db, app_key, supply_point, date_to
            )
        else:
            # Incremental: re-fetch the last stored day too, because E-Redes
            # revises recent readings (estimated -> real). Upsert dedupes.
            date_from = since.date() - timedelta(days=1)
            total, inserted, updated = _sync_forward(
                db, app_key, supply_point, date_from, date_to
            )
            if not backfill_done:
                # A previous walk-back was interrupted (watchdog kill or
                # token expiry) — continue it from the oldest stored
                # interval instead of leaving the deep history unfetched.
                oldest = first_ts(db, supply_point.id)
                if oldest is not None:
                    more, ins2, upd2, date_from = _walk_back_history(
                        db, app_key, supply_point, oldest.date() - timedelta(days=1)
                    )
                    total += more
                    inserted += ins2
                    updated += upd2
    except SessionExpiredError:
        raise_alert(
            db,
            "eredes_session_expired",
            "E-Redes session expired — reconnect in Settings.",
            dedup_key="eredes_session_expired",
        )
        notify_send(db, "Portinhola", "E-Redes session expired — tap to reconnect.")
        raise JobFailure("session_expired") from None

    if total == 0:
        raise JobFailure("no_data")

    return f"{total} intervals ({inserted} new, {updated} updated) from {date_from} to {date_to}"


def _persist_window(
    db: Session, supply_point_id: int, rows: list
) -> tuple[int, int]:
    """Upsert one window's rows and stamp last_sync immediately, so a
    killed or expired sync keeps everything fetched so far."""
    inserted, updated = upsert_intervals(
        db,
        supply_point_id,
        [(ts, kwh, "eredes_scrape", quality) for ts, kwh, quality in rows],
    )
    set_setting(db, "eredes_last_sync", datetime.now(UTC).isoformat())
    db.commit()
    return inserted, updated


def _sync_forward(
    db: Session, app_key: bytes, supply_point: SupplyPoint, date_from: date, date_to: date
) -> tuple[int, int, int]:
    total = inserted_total = updated_total = 0
    window_start = date_from
    while window_start <= date_to:
        window_end = min(window_start + timedelta(days=HISTORY_WINDOW_DAYS - 1), date_to)
        try:
            rows = fetch_consumption(
                db, app_key, supply_point.identifier, window_start, window_end
            )
        except EredesFetchError:
            rows = []
        if rows:
            inserted, updated = _persist_window(db, supply_point.id, rows)
            total += len(rows)
            inserted_total += inserted
            updated_total += updated
        window_start = window_end + timedelta(days=1)
    return total, inserted_total, updated_total


def _walk_back_history(
    db: Session, app_key: bytes, supply_point: SupplyPoint, date_to: date
) -> tuple[int, int, int, date]:
    """First sync: discover how far back the portal actually goes.

    Requests one window at a time, walking backwards, persisting each
    window as it lands, and stops after HISTORY_EMPTY_WINDOWS_TO_STOP
    consecutive empty windows — so we never have to guess a retention
    period and never lose progress to a timeout.
    """
    total = inserted_total = updated_total = 0
    oldest = date_to
    empty_streak = 0
    window_end = date_to
    days_walked = 0

    while empty_streak < HISTORY_EMPTY_WINDOWS_TO_STOP and days_walked < HISTORY_MAX_DAYS:
        window_start = window_end - timedelta(days=HISTORY_WINDOW_DAYS - 1)
        try:
            rows = fetch_consumption(
                db, app_key, supply_point.identifier, window_start, window_end
            )
        except EredesFetchError:
            rows = []
        if rows:
            empty_streak = 0
            inserted, updated = _persist_window(db, supply_point.id, rows)
            total += len(rows)
            inserted_total += inserted
            updated_total += updated
            oldest = window_start
        else:
            empty_streak += 1
        window_end = window_start - timedelta(days=1)
        days_walked += HISTORY_WINDOW_DAYS

    # The walk-back ran to the portal's horizon (or the hard cap) without
    # being interrupted — no need to ever repeat it.
    set_setting(db, "eredes_backfill_done", "1")
    db.commit()
    return total, inserted_total, updated_total, oldest


def _resolve_supply_point(db: Session) -> SupplyPoint | None:
    override = get_setting(db, "eredes_supply_point_id")
    if override:
        return db.get(SupplyPoint, int(override))
    return db.scalar(
        select(SupplyPoint)
        .where(SupplyPoint.utility == "electricity")
        .order_by(SupplyPoint.id)
    )
