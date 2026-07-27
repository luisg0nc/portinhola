from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.core.billdata import Utility
from portinhola.db.models import Contract, SupplyPoint

router = APIRouter(dependencies=[Depends(require_auth)])


class ContractIn(BaseModel):
    supplier_name: str
    supplier_nif: str
    tariff_name: str = ""
    power_kva: float | None = None
    cycle: str | None = None
    gas_tier: int | None = None
    start_date: date
    reading_day_start: int | None = None
    reading_day_end: int | None = None
    submit_url: str = ""
    submit_phone: str = ""
    submit_reference: str = ""


class ContractPatch(BaseModel):
    supplier_name: str | None = None
    supplier_nif: str | None = None
    tariff_name: str | None = None
    power_kva: float | None = None
    cycle: str | None = None
    gas_tier: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    reading_day_start: int | None = None
    reading_day_end: int | None = None
    submit_url: str | None = None
    submit_phone: str | None = None
    submit_reference: str | None = None


class ContractOut(BaseModel):
    id: int
    supplier_name: str
    supplier_nif: str
    tariff_name: str
    power_kva: float | None
    cycle: str | None
    gas_tier: int | None
    start_date: date
    end_date: date | None
    reading_day_start: int | None
    reading_day_end: int | None
    submit_url: str
    submit_phone: str
    submit_reference: str

    model_config = {"from_attributes": True}


class SupplyPointIn(BaseModel):
    utility: Utility
    identifier: str
    name: str = ""


class SupplyPointOut(BaseModel):
    id: int
    utility: str
    identifier: str
    name: str
    contracts: list[ContractOut]


def _supply_point_out(sp: SupplyPoint, contracts: list[Contract]) -> SupplyPointOut:
    return SupplyPointOut(
        id=sp.id,
        utility=sp.utility,
        identifier=sp.identifier,
        name=sp.name,
        contracts=[ContractOut.model_validate(c) for c in contracts],
    )


@router.get("")
def list_supply_points(db: Session = Depends(get_db)) -> list[SupplyPointOut]:
    result = []
    for sp in db.scalars(select(SupplyPoint).order_by(SupplyPoint.id)):
        contracts = list(
            db.scalars(
                select(Contract)
                .where(Contract.supply_point_id == sp.id)
                .order_by(Contract.start_date)
            )
        )
        result.append(_supply_point_out(sp, contracts))
    return result


@router.post("", status_code=201)
def create_supply_point(body: SupplyPointIn, db: Session = Depends(get_db)) -> SupplyPointOut:
    existing = db.scalar(select(SupplyPoint).where(SupplyPoint.identifier == body.identifier))
    if existing is not None:
        raise HTTPException(status_code=409, detail="identifier_exists")
    sp = SupplyPoint(utility=body.utility, identifier=body.identifier, name=body.name)
    db.add(sp)
    db.commit()
    return _supply_point_out(sp, [])


@router.post("/{sp_id}/contracts", status_code=201)
def create_contract(sp_id: int, body: ContractIn, db: Session = Depends(get_db)) -> ContractOut:
    sp = db.get(SupplyPoint, sp_id)
    if sp is None:
        raise HTTPException(status_code=404, detail="supply_point_not_found")
    open_contract = db.scalar(
        select(Contract).where(Contract.supply_point_id == sp_id, Contract.end_date.is_(None))
    )
    if open_contract is not None:
        open_contract.end_date = body.start_date - timedelta(days=1)
    contract = Contract(supply_point_id=sp_id, **body.model_dump())
    db.add(contract)
    db.commit()
    return ContractOut.model_validate(contract)


@router.patch("/contracts/{contract_id}")
def update_contract(
    contract_id: int, body: ContractPatch, db: Session = Depends(get_db)
) -> ContractOut:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="contract_not_found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(contract, field, value)
    db.commit()
    return ContractOut.model_validate(contract)
