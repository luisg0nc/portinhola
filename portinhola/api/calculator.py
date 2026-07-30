from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.core.promos import first_year_total
from portinhola.core.replay import BillSim, replay_electricity, replay_gas
from portinhola.core.tariffs import Tariff, load_tariffs, load_taxes
from portinhola.db.models import (
    Bill,
    BillLine,
    Contract,
    IntervalConsumption,
    SupplyPoint,
)
from portinhola.db.settings_repo import get_setting

router = APIRouter(dependencies=[Depends(require_auth)])

KVA_LADDER = [1.15, 2.3, 3.45, 4.6, 5.75, 6.9, 10.35, 13.8, 17.25, 20.7]


def _aware(ts: datetime) -> datetime:
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts


def _open_contract(db: Session, sp_id: int) -> Contract | None:
    return db.scalar(
        select(Contract).where(Contract.supply_point_id == sp_id, Contract.end_date.is_(None))
    )


def _current_tariff(
    db: Session, contract: Contract | None, tariffs: list[Tariff], utility: str
) -> Tariff | None:
    if contract is None:
        return None
    override = get_setting(db, f"tariff_override:{contract.id}")
    if override:
        return next((t for t in tariffs if t.id == override), None)
    candidates = [
        t
        for t in tariffs
        if t.utility == utility and t.supplier_nif == contract.supplier_nif
    ]
    return candidates[0] if candidates else None


def _consumption(
    db: Session, sp_id: int, start: datetime, end: datetime
) -> list[tuple[datetime, float]]:
    rows = db.scalars(
        select(IntervalConsumption)
        .where(
            IntervalConsumption.supply_point_id == sp_id,
            IntervalConsumption.ts >= start,
            IntervalConsumption.ts < end,
        )
        .order_by(IntervalConsumption.ts)
    )
    return [(_aware(r.ts), r.kwh) for r in rows]


def _result_row(tariff: Tariff, option: str, sim: BillSim, current_total: int | None) -> dict:
    return {
        "tariff_id": tariff.id,
        "supplier": tariff.supplier,
        "name": tariff.name,
        "option": option,
        "total_cents": sim.total_cents,
        "delta_cents": (sim.total_cents - current_total) if current_total is not None else None,
        "breakdown": sim.model_dump(),
        "valid_to": tariff.valid_to.isoformat() if tariff.valid_to else None,
        "retrieved": tariff.retrieved.isoformat(),
        "conditions": tariff.conditions,
        "first_year_total_cents": first_year_total(sim, tariff.promo),
        "promo": (
            {
                "energy_pct": tariff.promo.energy_pct,
                "fixed_pct": tariff.promo.fixed_pct,
                "months": tariff.promo.months,
            }
            if tariff.promo is not None
            else None
        ),
    }


@router.get("/electricity")
def electricity(
    supply_point_id: int,
    months: int = 12,
    kva: float | None = None,
    db: Session = Depends(get_db),
) -> dict:
    sp = db.get(SupplyPoint, supply_point_id)
    if sp is None:
        raise HTTPException(status_code=404, detail="supply_point_not_found")
    contract = _open_contract(db, supply_point_id)
    use_kva = kva or (contract.power_kva if contract and contract.power_kva else 4.6)

    last = db.scalar(
        select(func.max(IntervalConsumption.ts)).where(
            IntervalConsumption.supply_point_id == supply_point_id
        )
    )
    if last is None:
        raise HTTPException(status_code=422, detail="no_consumption_data")
    end_day = _aware(last).date()
    start_day = end_day - timedelta(days=months * 30 - 1)
    start = datetime.combine(start_day, time(0), tzinfo=UTC)
    end = datetime.combine(end_day + timedelta(days=1), time(0), tzinfo=UTC)
    consumption = _consumption(db, supply_point_id, start, end)
    days = (end_day - start_day).days + 1
    expected_slots = days * 96
    coverage = len(consumption) / expected_slots if expected_slots else 0.0
    total_kwh = sum(kwh for _, kwh in consumption)

    tariffs = load_tariffs()
    taxes = load_taxes()

    current_tariff = _current_tariff(db, contract, tariffs, "electricity")
    current_option = {"simples": "simples", "bi-horario": "bi", "tri-horario": "tri"}.get(
        (contract.cycle if contract else None) or "simples", "simples"
    )
    current_total: int | None = None
    if current_tariff is not None:
        try:
            current_total = replay_electricity(
                consumption, current_tariff, taxes, use_kva, current_option, start_day, end_day
            ).total_cents
        except ValueError:
            current_total = None

    results = []
    for tariff in tariffs:
        if tariff.utility != "electricity" or tariff.electricity is None:
            continue
        for option in tariff.electricity.energy_eur_kwh:
            try:
                sim = replay_electricity(
                    consumption, tariff, taxes, use_kva, option, start_day, end_day
                )
            except ValueError:
                continue
            results.append(_result_row(tariff, option, sim, current_total))
    results.sort(key=lambda r: r["total_cents"])

    return {
        "window": {
            "start": start_day.isoformat(),
            "end": end_day.isoformat(),
            "kwh": round(total_kwh, 1),
            "days": days,
            "coverage": round(coverage, 3),
        },
        "current": (
            {"tariff_id": current_tariff.id, "total_cents": current_total}
            if current_tariff is not None and current_total is not None
            else None
        ),
        "results": results,
    }


@router.get("/gas")
def gas(supply_point_id: int, months: int = 12, db: Session = Depends(get_db)) -> dict:
    sp = db.get(SupplyPoint, supply_point_id)
    if sp is None:
        raise HTTPException(status_code=404, detail="supply_point_not_found")
    contract = _open_contract(db, supply_point_id)
    tier = str(contract.gas_tier) if contract and contract.gas_tier else "2"

    cutoff = date.today() - timedelta(days=months * 30)  # noqa: DTZ011
    rows = db.execute(
        select(BillLine.quantity, BillLine.period_start, BillLine.period_end)
        .join(Bill, BillLine.bill_id == Bill.id)
        .join(Contract, BillLine.contract_id == Contract.id)
        .where(
            Contract.supply_point_id == supply_point_id,
            BillLine.category == "energy",
            BillLine.unit == "kWh",
            BillLine.quantity.is_not(None),
            Bill.issue_date >= cutoff,
        )
    ).all()
    total_kwh = sum(q for q, _, _ in rows if q)
    periods = [(ps, pe) for _, ps, pe in rows if ps and pe]
    if total_kwh <= 0:
        raise HTTPException(status_code=422, detail="no_gas_data")
    if periods:
        span_start = min(ps for ps, _ in periods)
        span_end = max(pe for _, pe in periods)
        days = max((span_end - span_start).days + 1, 1)
    else:
        days = months * 30

    tariffs = load_tariffs()
    taxes = load_taxes()
    current_tariff = _current_tariff(db, contract, tariffs, "gas")
    current_total: int | None = None
    if current_tariff is not None:
        try:
            current_total = replay_gas(total_kwh, days, current_tariff, taxes, tier).total_cents
        except ValueError:
            current_total = None

    results = []
    for tariff in tariffs:
        if tariff.utility != "gas" or tariff.gas is None:
            continue
        use_tier = tier if tier in tariff.gas.tiers else next(iter(tariff.gas.tiers))
        try:
            sim = replay_gas(total_kwh, days, tariff, taxes, use_tier)
        except ValueError:
            continue
        results.append(_result_row(tariff, f"escalao-{use_tier}", sim, current_total))
    results.sort(key=lambda r: r["total_cents"])

    return {
        "window": {"kwh": round(total_kwh, 1), "days": days},
        "current": (
            {"tariff_id": current_tariff.id, "total_cents": current_total}
            if current_tariff is not None and current_total is not None
            else None
        ),
        "results": results,
    }


@router.get("/potencia")
def potencia(supply_point_id: int, db: Session = Depends(get_db)) -> dict:
    contract = _open_contract(db, supply_point_id)
    contracted = contract.power_kva if contract and contract.power_kva else None
    row = db.execute(
        select(IntervalConsumption.ts, IntervalConsumption.kwh)
        .where(IntervalConsumption.supply_point_id == supply_point_id)
        .order_by(IntervalConsumption.kwh.desc())
        .limit(1)
    ).first()
    if row is None:
        raise HTTPException(status_code=422, detail="no_consumption_data")
    peak_kw = row.kwh * 4
    recommended = next((k for k in KVA_LADDER if k >= peak_kw), KVA_LADDER[-1])

    saving: int | None = None
    if contracted and recommended < contracted:
        tariffs = load_tariffs()
        current_tariff = _current_tariff(db, contract, tariffs, "electricity")
        if current_tariff and current_tariff.electricity:
            from portinhola.core.replay import _nearest_power_price

            prices = current_tariff.electricity.power_eur_day
            saving = round(
                (
                    _nearest_power_price(prices, contracted)
                    - _nearest_power_price(prices, recommended)
                )
                * 365.25
                * 100
            )

    return {
        "contracted_kva": contracted,
        "peak_kw": round(peak_kw, 2),
        "peak_at": _aware(row.ts).isoformat(),
        "recommended_kva": recommended,
        "saving_cents_year": saving,
    }


@router.get("/calibration")
def calibration(supply_point_id: int, bill_id: int, db: Session = Depends(get_db)) -> dict:
    bill = db.get(Bill, bill_id)
    if bill is None or bill.period_start is None or bill.period_end is None:
        raise HTTPException(status_code=404, detail="bill_not_found_or_no_period")
    contract = _open_contract(db, supply_point_id)
    if contract is None:
        raise HTTPException(status_code=422, detail="no_open_contract")

    tariffs = load_tariffs()
    taxes = load_taxes()
    current_tariff = _current_tariff(db, contract, tariffs, "electricity")
    if current_tariff is None:
        raise HTTPException(status_code=422, detail="no_current_tariff")

    start = datetime.combine(bill.period_start, time(0), tzinfo=UTC)
    end = datetime.combine(bill.period_end + timedelta(days=1), time(0), tzinfo=UTC)
    consumption = _consumption(db, supply_point_id, start, end)
    option = {"simples": "simples", "bi-horario": "bi", "tri-horario": "tri"}.get(
        contract.cycle or "simples", "simples"
    )
    sim = replay_electricity(
        consumption,
        current_tariff,
        taxes,
        contract.power_kva or 4.6,
        option,
        bill.period_start,
        bill.period_end,
    )
    actual = (
        db.scalar(
            select(func.coalesce(func.sum(BillLine.amount_cents), 0)).where(
                BillLine.bill_id == bill_id, BillLine.contract_id == contract.id
            )
        )
        or 0
    )
    return {
        "simulated_cents": sim.subtotal_cents,
        "actual_cents": actual,
        "delta_cents": sim.subtotal_cents - actual,
        "kwh": sim.energy_kwh,
    }


@router.get("/dual")
def dual(months: int = 12, db: Session = Depends(get_db)) -> dict:
    """Combined luz+gás ranking: supplier bundles (with sourced dual
    discounts), the best mixed pair, and the current combo."""
    from portinhola.core.dual import combine
    from portinhola.core.tariffs import load_dual_bundles

    elec_sp = db.scalar(
        select(SupplyPoint).where(SupplyPoint.utility == "electricity").order_by(SupplyPoint.id)
    )
    gas_sp = db.scalar(
        select(SupplyPoint).where(SupplyPoint.utility == "gas").order_by(SupplyPoint.id)
    )
    if elec_sp is None or gas_sp is None:
        raise HTTPException(status_code=404, detail="supply_point_not_found")

    tariffs = load_tariffs()
    taxes = load_taxes()
    bundles = load_dual_bundles(tariffs)

    # --- electricity sims (cheapest option per tariff, at the user's kVA)
    elec_contract = _open_contract(db, elec_sp.id)
    kva = elec_contract.power_kva if elec_contract and elec_contract.power_kva else 4.6
    last = db.scalar(
        select(func.max(IntervalConsumption.ts)).where(
            IntervalConsumption.supply_point_id == elec_sp.id
        )
    )
    if last is None:
        raise HTTPException(status_code=422, detail="no_consumption_data")
    end_day = _aware(last).date()
    start_day = end_day - timedelta(days=months * 30 - 1)
    consumption = _consumption(
        db,
        elec_sp.id,
        datetime.combine(start_day, time(0), tzinfo=UTC),
        datetime.combine(end_day + timedelta(days=1), time(0), tzinfo=UTC),
    )
    elec_days = (end_day - start_day).days + 1

    elec_sims: dict[str, BillSim] = {}
    for tariff in tariffs:
        if tariff.utility != "electricity" or tariff.electricity is None:
            continue
        best: BillSim | None = None
        for option in tariff.electricity.energy_eur_kwh:
            try:
                sim = replay_electricity(
                    consumption, tariff, taxes, kva, option, start_day, end_day
                )
            except ValueError:
                continue
            if best is None or sim.total_cents < best.total_cents:
                best = sim
        if best is not None:
            elec_sims[tariff.id] = best

    # --- gas sims (billed kWh window, user's tier)
    gas_contract = _open_contract(db, gas_sp.id)
    tier = str(gas_contract.gas_tier) if gas_contract and gas_contract.gas_tier else "2"
    cutoff = date.today() - timedelta(days=months * 30)  # noqa: DTZ011
    rows = db.execute(
        select(BillLine.quantity, BillLine.period_start, BillLine.period_end)
        .join(Bill, BillLine.bill_id == Bill.id)
        .join(Contract, BillLine.contract_id == Contract.id)
        .where(
            Contract.supply_point_id == gas_sp.id,
            BillLine.category == "energy",
            BillLine.unit == "kWh",
            BillLine.quantity.is_not(None),
            Bill.issue_date >= cutoff,
        )
    ).all()
    gas_kwh = sum(q for q, _, _ in rows if q)
    if gas_kwh <= 0:
        raise HTTPException(status_code=422, detail="no_gas_data")
    periods = [(ps, pe) for _, ps, pe in rows if ps and pe]
    gas_days = (
        max((max(pe for _, pe in periods) - min(ps for ps, _ in periods)).days + 1, 1)
        if periods
        else months * 30
    )

    gas_sims: dict[str, BillSim] = {}
    for tariff in tariffs:
        if tariff.utility != "gas" or tariff.gas is None:
            continue
        use_tier = tier if tier in tariff.gas.tiers else next(iter(tariff.gas.tiers))
        try:
            gas_sims[tariff.id] = replay_gas(gas_kwh, gas_days, tariff, taxes, use_tier)
        except ValueError:
            continue

    by_id = {t.id: t for t in tariffs}

    def _row(kind, supplier, name, elec_id, gas_id, bundle, conditions, no_data):
        result = combine(elec_sims[elec_id], gas_sims[gas_id], bundle, taxes)
        return {
            "kind": kind,
            "supplier": supplier,
            "name": name,
            "elec_total_cents": result.elec_total_cents,
            "gas_total_cents": result.gas_total_cents,
            "discount_cents": result.discount_cents,
            "total_cents": result.total_cents,
            "first_year_total_cents": result.first_year_total_cents,
            "delta_cents": None,
            "conditions": conditions,
            "no_discount_data": no_data,
        }

    results = []
    bundled_suppliers = set()
    for bundle in bundles:
        if bundle.electricity_tariff not in elec_sims or bundle.gas_tariff not in gas_sims:
            continue
        bundled_suppliers.add(by_id[bundle.electricity_tariff].supplier)
        results.append(
            _row(
                "bundle",
                bundle.supplier,
                bundle.name,
                bundle.electricity_tariff,
                bundle.gas_tariff,
                bundle,
                bundle.conditions,
                False,
            )
        )

    # suppliers with both fuels seeded but no dual file: plain sum, marked
    elec_by_supplier: dict[str, str] = {}
    for tid, sim in elec_sims.items():
        supplier = by_id[tid].supplier
        if (
            supplier not in elec_by_supplier
            or sim.total_cents < elec_sims[elec_by_supplier[supplier]].total_cents
        ):
            elec_by_supplier[supplier] = tid
    gas_by_supplier: dict[str, str] = {}
    for tid, sim in gas_sims.items():
        supplier = by_id[tid].supplier
        if (
            supplier not in gas_by_supplier
            or sim.total_cents < gas_sims[gas_by_supplier[supplier]].total_cents
        ):
            gas_by_supplier[supplier] = tid
    for supplier in sorted(set(elec_by_supplier) & set(gas_by_supplier) - bundled_suppliers):
        results.append(
            _row(
                "bundle",
                supplier,
                f"{supplier} Luz+Gás",
                elec_by_supplier[supplier],
                gas_by_supplier[supplier],
                None,
                None,
                True,
            )
        )

    # best mixed pair across all suppliers
    best_elec = min(elec_sims, key=lambda tid: elec_sims[tid].total_cents)
    best_gas = min(gas_sims, key=lambda tid: gas_sims[tid].total_cents)
    results.append(
        _row(
            "mixed",
            f"{by_id[best_elec].supplier} + {by_id[best_gas].supplier}",
            f"{by_id[best_elec].name} + {by_id[best_gas].name}",
            best_elec,
            best_gas,
            None,
            None,
            False,
        )
    )

    # current combo as delta baseline
    current_total = None
    elec_current = _current_tariff(db, elec_contract, tariffs, "electricity")
    gas_current = _current_tariff(db, gas_contract, tariffs, "gas")
    if (
        elec_current is not None
        and gas_current is not None
        and elec_current.id in elec_sims
        and gas_current.id in gas_sims
    ):
        current_row = _row(
            "current",
            f"{elec_current.supplier} + {gas_current.supplier}",
            f"{elec_current.name} + {gas_current.name}",
            elec_current.id,
            gas_current.id,
            None,
            None,
            False,
        )
        current_total = current_row["total_cents"]
        results.append(current_row)

    if current_total is not None:
        for row in results:
            row["delta_cents"] = row["total_cents"] - current_total
    results.sort(key=lambda r: r["total_cents"])

    return {
        "window": {
            "elec_kwh": round(sum(kwh for _, kwh in consumption), 1),
            "elec_days": elec_days,
            "gas_kwh": round(gas_kwh, 1),
            "gas_days": gas_days,
        },
        "results": results,
    }
