from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.db.models import Bill, BillLine, Contract, SupplyPoint

router = APIRouter(dependencies=[Depends(require_auth)])

CATEGORIES = ("energy", "power", "fixed", "tax", "other")


def _month_floor(day: date, months_back: int) -> date:
    year = day.year
    month = day.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


@router.get("/costs")
def costs(months: int = 13, db: Session = Depends(get_db)) -> dict:
    today = date.today()  # noqa: DTZ011 - server-local month bucketing is fine here
    cutoff = _month_floor(today, months - 1)

    utility_by_contract: dict[int, str] = {}
    for contract in db.scalars(select(Contract)):
        sp = db.get(SupplyPoint, contract.supply_point_id)
        if sp is not None:
            utility_by_contract[contract.id] = sp.utility

    buckets: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    for bill in db.scalars(select(Bill).where(Bill.issue_date >= cutoff)):
        month_key = bill.issue_date.strftime("%Y-%m")
        for line in bill.lines:
            utility = (
                utility_by_contract.get(line.contract_id, "unknown")
                if line.contract_id is not None
                else "unknown"
            )
            per_utility = buckets[month_key].setdefault(
                utility, {category: 0 for category in (*CATEGORIES, "total")}
            )
            per_utility[line.category] += line.amount_cents
            per_utility["total"] += line.amount_cents

    return {
        "months": [
            {"month": month, "by_utility": buckets[month]} for month in sorted(buckets)
        ]
    }


@router.get("/estimate")
def estimate(supply_point_id: int, db: Session = Depends(get_db)) -> dict:
    from portinhola.api.calculator import _consumption, _current_tariff, _open_contract
    from portinhola.core.replay import replay_electricity
    from portinhola.core.tariffs import load_tariffs, load_taxes

    contract = _open_contract(db, supply_point_id)
    if contract is None:
        raise HTTPException(status_code=422, detail="no_open_contract")
    tariff = _current_tariff(db, contract, load_tariffs(), "electricity")
    if tariff is None:
        raise HTTPException(status_code=422, detail="no_current_tariff")

    # Billing period anchor: day after the last billed period for this
    # contract; fallback to the calendar month.
    last_period_end = db.scalar(
        select(func.max(Bill.period_end))
        .join(BillLine, BillLine.bill_id == Bill.id)
        .where(BillLine.contract_id == contract.id)
    )
    today = datetime.now(UTC).date()
    period_start = (
        last_period_end + timedelta(days=1) if last_period_end else today.replace(day=1)
    )
    if period_start > today:
        period_start = today.replace(day=1)

    start = datetime.combine(period_start, time(0), tzinfo=UTC)
    end = datetime.combine(today + timedelta(days=1), time(0), tzinfo=UTC)
    consumption = _consumption(db, supply_point_id, start, end)
    days = (today - period_start).days + 1
    option = {"simples": "simples", "bi-horario": "bi", "tri-horario": "tri"}.get(
        contract.cycle or "simples", "simples"
    )
    sim = replay_electricity(
        consumption,
        tariff,
        load_taxes(),
        contract.power_kva or 4.6,
        option,
        period_start,
        today,
    )
    expected_slots = days * 96
    return {
        "period_start": period_start.isoformat(),
        "kwh": sim.energy_kwh,
        "estimated_cents": sim.total_cents,
        "coverage": round(len(consumption) / expected_slots, 3) if expected_slots else 0.0,
    }
