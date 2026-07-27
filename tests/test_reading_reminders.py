from datetime import UTC, date, datetime

from sqlalchemy import select

from portinhola.db.models import Alert, Contract, Reading, SupplyPoint
from portinhola.jobs import reading_reminders


def _setup(db, day_start=7, day_end=9) -> int:
    sp = SupplyPoint(utility="gas", identifier="SP-GASR", name="Casa")
    db.add(sp)
    db.flush()
    db.add(
        Contract(
            supply_point_id=sp.id,
            supplier_name="G9",
            supplier_nif="504435302",
            start_date=date(2026, 1, 1),
            reading_day_start=day_start,
            reading_day_end=day_end,
        )
    )
    db.commit()
    return sp.id


def test_reminder_inside_window_once(app, monkeypatch) -> None:
    monkeypatch.setattr(reading_reminders, "_today", lambda: date(2026, 7, 8))
    notifications: list[str] = []
    monkeypatch.setattr(
        reading_reminders, "notify_send", lambda db, t, b: notifications.append(t) or True
    )
    with app.state.sessionmaker() as db:
        _setup(db)
        reading_reminders.reading_reminders(db)
        reading_reminders.reading_reminders(db)
        alerts = db.scalars(select(Alert).where(Alert.type == "reading_reminder")).all()
        assert len(alerts) == 1
        assert len(notifications) == 1


def test_no_reminder_when_reading_exists(app, monkeypatch) -> None:
    monkeypatch.setattr(reading_reminders, "_today", lambda: date(2026, 7, 8))
    monkeypatch.setattr(reading_reminders, "notify_send", lambda db, t, b: True)
    with app.state.sessionmaker() as db:
        sp_id = _setup(db)
        db.add(
            Reading(
                supply_point_id=sp_id,
                register="Total",
                value=10.0,
                taken_at=datetime(2026, 7, 7, 12, 0, tzinfo=UTC),
            )
        )
        db.commit()
        reading_reminders.reading_reminders(db)
        assert db.scalars(select(Alert)).all() == []


def test_no_reminder_outside_window(app, monkeypatch) -> None:
    monkeypatch.setattr(reading_reminders, "_today", lambda: date(2026, 7, 15))
    monkeypatch.setattr(reading_reminders, "notify_send", lambda db, t, b: True)
    with app.state.sessionmaker() as db:
        _setup(db)
        reading_reminders.reading_reminders(db)
        assert db.scalars(select(Alert)).all() == []
