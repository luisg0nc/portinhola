import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.core.billdata import BillData, Category, Utility
from portinhola.core.fiscal_qr import FiscalQR
from portinhola.core.pdf import extract_pdf
from portinhola.db.models import Bill, BillLine, Contract, SupplyPoint
from portinhola.extractors.base import get_extractor


class SupplyMatch(BaseModel):
    identifier: str
    supply_point_id: int | None
    contract_id: int | None


class UploadDraft(BaseModel):
    upload_token: str
    qr: FiscalQR | None
    parsed: BillData | None
    extractor: str | None
    supply_matches: list[SupplyMatch]
    duplicate_of: int | None


class NewContractIn(BaseModel):
    supplier_name: str
    supplier_nif: str
    tariff_name: str = ""
    power_kva: float | None = None
    cycle: str | None = None
    gas_tier: int | None = None
    start_date: date


class NewSupplyPointIn(BaseModel):
    utility: Utility
    identifier: str
    name: str = ""
    contract: NewContractIn


class ConfirmLine(BaseModel):
    description: str
    category: Category
    utility: Utility | None = None
    period_start: date | None = None
    period_end: date | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    amount_cents: int
    vat_rate: int | None = None
    contract_id: int | None = None


class ConfirmBill(BaseModel):
    issuer_nif: str
    customer_nif: str | None = None
    doc_type: str = "FT"
    doc_number: str
    atcud: str | None = None
    issue_date: date
    period_start: date | None = None
    period_end: date | None = None
    total_cents: int
    vat_fields: dict[str, str] = {}
    parse_status: str
    extractor: str | None = None
    qr_raw: str | None = None


class ConfirmPayload(BaseModel):
    upload_token: str | None
    bill: ConfirmBill
    lines: list[ConfirmLine]
    new_supply_points: list[NewSupplyPointIn]


def analyze_upload(path: Path, db: Session) -> tuple[FiscalQR | None, BillData | None, str | None, list[SupplyMatch], int | None]:
    extracted = extract_pdf(path)
    qr = extracted.qr
    parsed: BillData | None = None
    extractor_name: str | None = None
    duplicate_of: int | None = None

    if qr is not None:
        if qr.atcud:
            existing = db.scalar(select(Bill).where(Bill.atcud == qr.atcud))
            if existing is not None:
                duplicate_of = existing.id
        extractor = get_extractor(qr.issuer_nif)
        if extractor is not None:
            extractor_name = extractor.name
            try:
                parsed = extractor.parse(extracted.pages)
            except Exception:  # noqa: BLE001 - any extractor failure degrades to QR-only
                parsed = None

    matches: list[SupplyMatch] = []
    if parsed is not None:
        for supply in parsed.supplies:
            sp = db.scalar(select(SupplyPoint).where(SupplyPoint.identifier == supply.identifier))
            contract = None
            if sp is not None:
                contract = db.scalar(
                    select(Contract).where(
                        Contract.supply_point_id == sp.id, Contract.end_date.is_(None)
                    )
                )
            matches.append(
                SupplyMatch(
                    identifier=supply.identifier,
                    supply_point_id=sp.id if sp else None,
                    contract_id=contract.id if contract else None,
                )
            )
    return qr, parsed, extractor_name, matches, duplicate_of


def confirm(payload: ConfirmPayload, db: Session, uploads_dir: Path, bills_dir: Path) -> Bill:
    if payload.bill.atcud:
        existing = db.scalar(select(Bill).where(Bill.atcud == payload.bill.atcud))
        if existing is not None:
            raise DuplicateAtcudError(existing.id)

    new_contract_ids: list[int] = []
    for new_sp in payload.new_supply_points:
        sp = db.scalar(select(SupplyPoint).where(SupplyPoint.identifier == new_sp.identifier))
        if sp is None:
            sp = SupplyPoint(utility=new_sp.utility, identifier=new_sp.identifier, name=new_sp.name)
            db.add(sp)
            db.flush()
        contract = Contract(supply_point_id=sp.id, **new_sp.contract.model_dump())
        db.add(contract)
        db.flush()
        new_contract_ids.append(contract.id)

    bill = Bill(
        issuer_nif=payload.bill.issuer_nif,
        customer_nif=payload.bill.customer_nif,
        doc_type=payload.bill.doc_type,
        doc_number=payload.bill.doc_number,
        atcud=payload.bill.atcud,
        issue_date=payload.bill.issue_date,
        period_start=payload.bill.period_start,
        period_end=payload.bill.period_end,
        total_cents=payload.bill.total_cents,
        vat_json=json.dumps(payload.bill.vat_fields),
        parse_status=payload.bill.parse_status,
        extractor=payload.bill.extractor,
        qr_raw=payload.bill.qr_raw,
    )
    for line in payload.lines:
        contract_id = line.contract_id
        if contract_id is not None and contract_id < 0:
            index = -contract_id - 1
            if index >= len(new_contract_ids):
                raise InvalidContractRefError(contract_id)
            contract_id = new_contract_ids[index]
        bill.lines.append(
            BillLine(
                contract_id=contract_id,
                description=line.description,
                category=line.category,
                period_start=line.period_start,
                period_end=line.period_end,
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price,
                amount_cents=line.amount_cents,
                vat_rate=line.vat_rate,
            )
        )
    db.add(bill)
    db.flush()

    if payload.upload_token:
        source = uploads_dir / f"{payload.upload_token}.pdf"
        if source.exists():
            bills_dir.mkdir(parents=True, exist_ok=True)
            target = bills_dir / f"{bill.id}.pdf"
            source.rename(target)
            bill.pdf_path = str(target)

    db.commit()
    return bill


class DuplicateAtcudError(Exception):
    def __init__(self, bill_id: int) -> None:
        self.bill_id = bill_id


class InvalidContractRefError(Exception):
    def __init__(self, ref: int) -> None:
        self.ref = ref
