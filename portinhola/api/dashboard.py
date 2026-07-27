from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.db.models import Bill, Contract, SupplyPoint

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
