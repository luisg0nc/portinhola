from datetime import UTC, datetime

from portinhola.db.consumption_repo import last_ts, upsert_intervals
from portinhola.db.models import IntervalConsumption, SupplyPoint


def _make_sp(db) -> int:
    sp = SupplyPoint(utility="electricity", identifier="PT000TEST1", name="Casa")
    db.add(sp)
    db.commit()
    return sp.id


def test_upsert_inserts_then_updates(app) -> None:
    ts = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    with app.state.sessionmaker() as db:
        sp_id = _make_sp(db)
        inserted, updated = upsert_intervals(db, sp_id, [(ts, 0.25, "file_import", "real")])
        assert (inserted, updated) == (1, 0)
        inserted, updated = upsert_intervals(db, sp_id, [(ts, 0.30, "eredes_scrape", "real")])
        assert (inserted, updated) == (0, 1)
        rows = db.query(IntervalConsumption).all()
        assert len(rows) == 1
        assert rows[0].kwh == 0.30
        assert rows[0].source == "eredes_scrape"


def test_last_ts(app) -> None:
    with app.state.sessionmaker() as db:
        sp_id = _make_sp(db)
        assert last_ts(db, sp_id) is None
        upsert_intervals(
            db,
            sp_id,
            [
                (datetime(2026, 7, 1, 10, 0, tzinfo=UTC), 0.1, "file_import", "real"),
                (datetime(2026, 7, 1, 10, 15, tzinfo=UTC), 0.2, "file_import", "real"),
            ],
        )
        assert last_ts(db, sp_id) == datetime(2026, 7, 1, 10, 15, tzinfo=UTC)
