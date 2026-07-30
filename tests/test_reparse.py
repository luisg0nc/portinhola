from datetime import date
from types import SimpleNamespace

from sqlalchemy import select

from portinhola.core.ingest import reparse_partial_bills
from portinhola.db.models import Bill, Contract, SupplyPoint
from tests.fixtures.loader import load_pages


def _setup(db, tmp_path, issuer_nif: str) -> Bill:
    for utility, identifier in (
        ("electricity", "PT0002000000000000XX"),
        ("gas", "PT1601000000000000XX"),
    ):
        sp = SupplyPoint(utility=utility, identifier=identifier, name="Casa")
        db.add(sp)
        db.flush()
        db.add(
            Contract(
                supply_point_id=sp.id,
                supplier_name="EDP Comercial",
                supplier_nif=issuer_nif,
                start_date=date(2022, 1, 1),
            )
        )
    pdf = tmp_path / "bill.pdf"
    pdf.write_bytes(b"%PDF-fake")
    bill = Bill(
        issuer_nif=issuer_nif,
        doc_number="FT2022 34/340000000001",
        issue_date=date(2022, 12, 12),
        total_cents=9796,
        parse_status="partial",
        pdf_path=str(pdf),
    )
    db.add(bill)
    db.commit()
    return bill


def test_reparse_fills_lines_and_assigns_contracts(app, monkeypatch, tmp_path) -> None:
    pages = load_pages("edp/pages_2022-12.txt")
    monkeypatch.setattr(
        "portinhola.core.ingest.extract_pdf",
        lambda path: SimpleNamespace(pages=pages, qr=None),
    )
    with app.state.sessionmaker() as db:
        bill = _setup(db, tmp_path, "503504564")
        reparsed, skipped = reparse_partial_bills(db)
        assert (reparsed, skipped) == (1, 0)
        refreshed = db.scalar(select(Bill).where(Bill.id == bill.id))
        assert refreshed.parse_status == "parsed"
        assert refreshed.extractor == "edp"
        assert len(refreshed.lines) == 28
        elec_lines = [line for line in refreshed.lines if line.contract_id is not None]
        assert elec_lines, "lines must be assigned to the open contracts"
        assert str(refreshed.period_start) == "2022-10-25"


def test_reparse_skips_bills_without_extractor_or_pdf(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "portinhola.core.ingest.extract_pdf",
        lambda path: SimpleNamespace(pages=[], qr=None),
    )
    with app.state.sessionmaker() as db:
        db.add(
            Bill(
                issuer_nif="999999990",  # no extractor registered
                doc_number="X/1",
                issue_date=date(2024, 1, 1),
                total_cents=100,
                parse_status="partial",
            )
        )
        db.commit()
        assert reparse_partial_bills(db) == (0, 1)
