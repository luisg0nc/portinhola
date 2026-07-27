from datetime import date

from portinhola.db.models import Bill, BillLine, Contract, SupplyPoint


def test_supply_point_contract_bill_roundtrip(app) -> None:
    with app.state.sessionmaker() as db:
        sp = SupplyPoint(utility="electricity", identifier="PT0002000000000001AA", name="Casa")
        db.add(sp)
        db.flush()
        contract = Contract(
            supply_point_id=sp.id,
            supplier_name="G9",
            supplier_nif="504435302",
            power_kva=4.6,
            cycle="simples",
            start_date=date(2024, 1, 1),
        )
        db.add(contract)
        db.flush()
        bill = Bill(
            issuer_nif="504435302",
            doc_number="FC FAE/0000001",
            atcud="TESTTEST-1",
            issue_date=date(2026, 7, 9),
            total_cents=8536,
            parse_status="parsed",
        )
        bill.lines.append(
            BillLine(
                contract_id=contract.id,
                description="Eletricidade - energia",
                category="energy",
                quantity=200.0,
                unit="kWh",
                unit_price=0.094,
                amount_cents=1880,
                vat_rate=6,
            )
        )
        db.add(bill)
        db.commit()
        assert bill.id is not None
        assert bill.lines[0].contract_id == contract.id


def test_bill_lines_cascade_delete(app) -> None:
    with app.state.sessionmaker() as db:
        bill = Bill(
            issuer_nif="505084040",
            doc_number="FAC 1",
            issue_date=date(2026, 7, 21),
            total_cents=3911,
            parse_status="manual",
        )
        bill.lines.append(
            BillLine(description="Consumo Água", category="energy", amount_cents=1909)
        )
        db.add(bill)
        db.commit()
        db.delete(bill)
        db.commit()
        assert db.query(BillLine).count() == 0
