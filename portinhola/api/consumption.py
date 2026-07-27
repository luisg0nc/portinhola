import tempfile
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.db.consumption_repo import upsert_intervals
from portinhola.db.models import IntervalConsumption, SupplyPoint
from portinhola.integrations.eredes_xlsx import parse_eredes_xlsx

router = APIRouter(dependencies=[Depends(require_auth)])

LISBON = ZoneInfo("Europe/Lisbon")


def _aware(ts: datetime) -> datetime:
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts


def _slots(db: Session, supply_point_id: int, start: datetime, end: datetime):
    return db.scalars(
        select(IntervalConsumption)
        .where(
            IntervalConsumption.supply_point_id == supply_point_id,
            IntervalConsumption.ts >= start,
            IntervalConsumption.ts < end,
        )
        .order_by(IntervalConsumption.ts)
    )


@router.post("/import")
def import_file(
    file: UploadFile,
    supply_point_id: int = Form(...),
    force: bool = Form(False),
    db: Session = Depends(get_db),
) -> dict:
    sp = db.get(SupplyPoint, supply_point_id)
    if sp is None:
        raise HTTPException(status_code=404, detail="supply_point_not_found")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = Path(tmp.name)
    try:
        export = parse_eredes_xlsx(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    if export.cpe is not None and export.cpe != sp.identifier and not force:
        raise HTTPException(status_code=422, detail="cpe_mismatch")
    if not export.rows:
        raise HTTPException(status_code=422, detail="no_data_rows")

    inserted, updated = upsert_intervals(
        db,
        supply_point_id,
        [(ts, kwh, "file_import", quality) for ts, kwh, quality in export.rows],
    )
    timestamps = [ts for ts, _, _ in export.rows]
    return {
        "inserted": inserted,
        "updated": updated,
        "from_ts": min(timestamps).isoformat(),
        "to_ts": max(timestamps).isoformat(),
    }


@router.get("/day")
def day_view(supply_point_id: int, date: str, db: Session = Depends(get_db)) -> list[dict]:
    year, month, day = (int(p) for p in date.split("-"))
    local_start = datetime(year, month, day, tzinfo=LISBON)
    start = local_start.astimezone(UTC)
    end = (local_start + timedelta(days=1)).astimezone(UTC)
    return [
        {"ts": _aware(row.ts).isoformat(), "kwh": row.kwh, "quality": row.quality}
        for row in _slots(db, supply_point_id, start, end)
    ]


@router.get("/month")
def month_view(supply_point_id: int, month: str, db: Session = Depends(get_db)) -> list[dict]:
    year, month_num = (int(p) for p in month.split("-"))
    local_start = datetime(year, month_num, 1, tzinfo=LISBON)
    next_month = (
        datetime(year + 1, 1, 1, tzinfo=LISBON)
        if month_num == 12
        else datetime(year, month_num + 1, 1, tzinfo=LISBON)
    )
    totals: dict[str, float] = defaultdict(float)
    for row in _slots(db, supply_point_id, local_start.astimezone(UTC), next_month.astimezone(UTC)):
        local_day = _aware(row.ts).astimezone(LISBON).date().isoformat()
        totals[local_day] += row.kwh
    return [{"date": day, "kwh": round(kwh, 3)} for day, kwh in sorted(totals.items())]


@router.get("/year")
def year_view(supply_point_id: int, year: int, db: Session = Depends(get_db)) -> list[dict]:
    local_start = datetime(year, 1, 1, tzinfo=LISBON)
    local_end = datetime(year + 1, 1, 1, tzinfo=LISBON)
    totals: dict[str, float] = defaultdict(float)
    for row in _slots(db, supply_point_id, local_start.astimezone(UTC), local_end.astimezone(UTC)):
        key = _aware(row.ts).astimezone(LISBON).strftime("%Y-%m")
        totals[key] += row.kwh
    return [{"month": month, "kwh": round(kwh, 3)} for month, kwh in sorted(totals.items())]


@router.get("/range")
def range_view(
    supply_point_id: int, start: datetime, end: datetime, db: Session = Depends(get_db)
) -> list[dict]:
    return [
        {"ts": _aware(row.ts).isoformat(), "kwh": row.kwh, "quality": row.quality}
        for row in _slots(db, supply_point_id, start, end)
    ]


@router.get("/status")
def status_view(supply_point_id: int, db: Session = Depends(get_db)) -> dict:
    first, last, count = db.execute(
        select(
            func.min(IntervalConsumption.ts),
            func.max(IntervalConsumption.ts),
            func.count(),
        ).where(IntervalConsumption.supply_point_id == supply_point_id)
    ).one()
    return {
        "first_ts": _aware(first).isoformat() if first else None,
        "last_ts": _aware(last).isoformat() if last else None,
        "count": count,
    }
