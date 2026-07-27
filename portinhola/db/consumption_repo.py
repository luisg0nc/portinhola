from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from portinhola.db.models import IntervalConsumption

IntervalRowTuple = tuple[datetime, float, str, str]


def upsert_intervals(
    db: Session, supply_point_id: int, rows: Iterable[IntervalRowTuple]
) -> tuple[int, int]:
    inserted = 0
    updated = 0
    for ts, kwh, source, quality in rows:
        stmt = insert(IntervalConsumption).values(
            supply_point_id=supply_point_id, ts=ts, kwh=kwh, source=source, quality=quality
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["supply_point_id", "ts"],
            set_={"kwh": kwh, "source": source, "quality": quality},
        )
        existed = db.scalar(
            select(func.count())
            .select_from(IntervalConsumption)
            .where(
                IntervalConsumption.supply_point_id == supply_point_id,
                IntervalConsumption.ts == ts,
            )
        )
        db.execute(stmt)
        if existed:
            updated += 1
        else:
            inserted += 1
    db.commit()
    return inserted, updated


def last_ts(db: Session, supply_point_id: int) -> datetime | None:
    value = db.scalar(
        select(func.max(IntervalConsumption.ts)).where(
            IntervalConsumption.supply_point_id == supply_point_id
        )
    )
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
