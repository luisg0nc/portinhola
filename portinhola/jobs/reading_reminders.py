from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.core.alerts import raise_alert
from portinhola.core.notify import send as notify_send
from portinhola.db.models import Contract, Reading, SupplyPoint
from portinhola.jobs.registry import job

LISBON = ZoneInfo("Europe/Lisbon")


def _today() -> date:
    return datetime.now(LISBON).date()


@job("reading_reminders")
def reading_reminders(db: Session) -> str:
    today = _today()
    reminded = 0
    contracts = db.scalars(
        select(Contract).where(
            Contract.end_date.is_(None),
            Contract.reading_day_start.is_not(None),
            Contract.reading_day_end.is_not(None),
        )
    )
    for contract in contracts:
        day_start = contract.reading_day_start
        day_end = contract.reading_day_end
        if day_start is None or day_end is None:
            continue
        if not (day_start <= today.day <= day_end):
            continue
        window_start = datetime(
            today.year, today.month, day_start, tzinfo=LISBON
        ).astimezone(UTC)
        has_reading = (
            db.scalar(
                select(Reading.id)
                .where(
                    Reading.supply_point_id == contract.supply_point_id,
                    Reading.taken_at >= window_start,
                )
                .limit(1)
            )
            is not None
        )
        if has_reading:
            continue
        sp = db.get(SupplyPoint, contract.supply_point_id)
        name = sp.name or sp.identifier if sp else str(contract.supply_point_id)
        _, created = raise_alert(
            db,
            "reading_reminder",
            f"Reading window open for {name} (until day {day_end}).",
            dedup_key=f"reading_reminder:{contract.supply_point_id}:{today.strftime('%Y-%m')}",
        )
        if created:
            notify_send(
                db,
                "Portinhola",
                f"Time to submit the meter reading for {name}.",
            )
            reminded += 1
    return f"{reminded} reminder(s) raised"
