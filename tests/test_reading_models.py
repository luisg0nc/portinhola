from datetime import UTC, datetime

from portinhola.core.readings import REGISTERS_BY_UTILITY, latest_readings
from portinhola.db.models import Reading, SupplyPoint


def _make_sp(db, utility: str = "gas") -> int:
    sp = SupplyPoint(utility=utility, identifier=f"SP-{utility}", name="Casa")
    db.add(sp)
    db.commit()
    return sp.id


def test_registers_by_utility() -> None:
    assert REGISTERS_BY_UTILITY["electricity"] == ["Vazio", "Cheias", "Ponta"]
    assert REGISTERS_BY_UTILITY["gas"] == ["Total"]
    assert REGISTERS_BY_UTILITY["water"] == ["Total"]


def test_reading_roundtrip_and_latest(app) -> None:
    with app.state.sessionmaker() as db:
        sp_id = _make_sp(db)
        db.add(
            Reading(
                supply_point_id=sp_id,
                register="Total",
                value=3384.0,
                taken_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            )
        )
        db.add(
            Reading(
                supply_point_id=sp_id,
                register="Total",
                value=3400.0,
                taken_at=datetime(2026, 7, 20, 10, 0, tzinfo=UTC),
            )
        )
        db.commit()
        latest = latest_readings(db, sp_id)
        assert latest["Total"].value == 3400.0
        assert latest["Total"].submission_status == "not_submitted"


def test_contract_window_fields(app) -> None:
    from datetime import date

    from portinhola.db.models import Contract

    with app.state.sessionmaker() as db:
        sp_id = _make_sp(db, "water")
        contract = Contract(
            supply_point_id=sp_id,
            supplier_name="Be Water",
            supplier_nif="505084040",
            start_date=date(2026, 1, 1),
            reading_day_start=14,
            reading_day_end=17,
            submit_phone="800 205 484",
            submit_reference="0464960186",
        )
        db.add(contract)
        db.commit()
        assert db.get(Contract, contract.id).reading_day_end == 17
