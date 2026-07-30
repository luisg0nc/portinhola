import json
import secrets
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.core import ingest
from portinhola.core.ingest import (
    ConfirmPayload,
    DuplicateAtcudError,
    InvalidContractRefError,
    UploadDraft,
)
from portinhola.db.models import Bill, Contract, SupplyPoint

router = APIRouter(dependencies=[Depends(require_auth)])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _uploads_dir(request: Request) -> Path:
    return request.app.state.config.data_dir / "uploads"


def _bills_dir(request: Request) -> Path:
    return request.app.state.config.data_dir / "bills"


class BillListItem(BaseModel):
    id: int
    issuer_nif: str
    doc_number: str
    issue_date: date
    period_start: date | None
    period_end: date | None
    total_cents: int
    parse_status: str
    utilities: list[str]
    supplier_name: str | None
    line_count: int


class BillLineOut(BaseModel):
    id: int
    contract_id: int | None
    description: str
    category: str
    period_start: date | None
    period_end: date | None
    quantity: float | None
    unit: str | None
    unit_price: float | None
    amount_cents: int
    vat_rate: int | None

    model_config = {"from_attributes": True}


class BillDetail(BaseModel):
    id: int
    issuer_nif: str
    customer_nif: str | None
    doc_type: str
    doc_number: str
    atcud: str | None
    issue_date: date
    period_start: date | None
    period_end: date | None
    total_cents: int
    vat_fields: dict[str, str]
    parse_status: str
    extractor: str | None
    pdf_available: bool
    lines: list[BillLineOut]


def _bill_utilities(bill: Bill, db: Session) -> tuple[list[str], str | None]:
    utilities: set[str] = set()
    supplier: str | None = None
    for line in bill.lines:
        if line.contract_id is None:
            continue
        contract = db.get(Contract, line.contract_id)
        if contract is None:
            continue
        supplier = supplier or contract.supplier_name
        sp = db.get(SupplyPoint, contract.supply_point_id)
        if sp is not None:
            utilities.add(sp.utility)
    return sorted(utilities), supplier


@router.post("/reparse")
def reparse_bills(db: Session = Depends(get_db)) -> dict:
    """Re-run extractors over stored PDFs of partial bills — used after a
    new supplier extractor ships."""
    reparsed, skipped = ingest.reparse_partial_bills(db)
    return {"reparsed": reparsed, "skipped": skipped}


@router.post("/upload")
def upload_bill(file: UploadFile, request: Request, db: Session = Depends(get_db)) -> UploadDraft:
    if file.content_type not in ("application/pdf", "application/x-pdf") and not (
        file.filename or ""
    ).lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="pdf_required")
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")

    token = secrets.token_urlsafe(16)
    uploads_dir = _uploads_dir(request)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    path = uploads_dir / f"{token}.pdf"
    path.write_bytes(content)

    qr, parsed, extractor_name, matches, duplicate_of = ingest.analyze_upload(path, db)
    return UploadDraft(
        upload_token=token,
        qr=qr,
        parsed=parsed,
        extractor=extractor_name,
        supply_matches=matches,
        duplicate_of=duplicate_of,
    )


@router.post("/confirm", status_code=201)
def confirm_bill(
    payload: ConfirmPayload, request: Request, db: Session = Depends(get_db)
) -> dict[str, int]:
    try:
        bill = ingest.confirm(payload, db, _uploads_dir(request), _bills_dir(request))
    except DuplicateAtcudError as exc:
        raise HTTPException(status_code=409, detail="duplicate_atcud") from exc
    except InvalidContractRefError as exc:
        raise HTTPException(status_code=422, detail="invalid_contract_ref") from exc
    return {"id": bill.id}


@router.get("")
def list_bills(
    utility: str | None = None, db: Session = Depends(get_db)
) -> list[BillListItem]:
    items = []
    for bill in db.scalars(select(Bill).order_by(Bill.issue_date.desc(), Bill.id.desc())):
        utilities, supplier = _bill_utilities(bill, db)
        if utility is not None and utility not in utilities:
            continue
        items.append(
            BillListItem(
                id=bill.id,
                issuer_nif=bill.issuer_nif,
                doc_number=bill.doc_number,
                issue_date=bill.issue_date,
                period_start=bill.period_start,
                period_end=bill.period_end,
                total_cents=bill.total_cents,
                parse_status=bill.parse_status,
                utilities=utilities,
                supplier_name=supplier,
                line_count=len(bill.lines),
            )
        )
    return items


@router.get("/{bill_id}")
def bill_detail(bill_id: int, db: Session = Depends(get_db)) -> BillDetail:
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="bill_not_found")
    return BillDetail(
        id=bill.id,
        issuer_nif=bill.issuer_nif,
        customer_nif=bill.customer_nif,
        doc_type=bill.doc_type,
        doc_number=bill.doc_number,
        atcud=bill.atcud,
        issue_date=bill.issue_date,
        period_start=bill.period_start,
        period_end=bill.period_end,
        total_cents=bill.total_cents,
        vat_fields=json.loads(bill.vat_json),
        parse_status=bill.parse_status,
        extractor=bill.extractor,
        pdf_available=bill.pdf_path is not None and Path(bill.pdf_path).exists(),
        lines=[BillLineOut.model_validate(line) for line in bill.lines],
    )


@router.get("/{bill_id}/pdf")
def bill_pdf(bill_id: int, db: Session = Depends(get_db)) -> FileResponse:
    bill = db.get(Bill, bill_id)
    if bill is None or bill.pdf_path is None or not Path(bill.pdf_path).exists():
        raise HTTPException(status_code=404, detail="pdf_not_found")
    return FileResponse(bill.pdf_path, media_type="application/pdf")


@router.delete("/{bill_id}", status_code=204)
def delete_bill(bill_id: int, db: Session = Depends(get_db)) -> None:
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="bill_not_found")
    if bill.pdf_path and Path(bill.pdf_path).exists():
        Path(bill.pdf_path).unlink()
    db.delete(bill)
    db.commit()
