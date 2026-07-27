from datetime import UTC, datetime

from sqlalchemy import select

from portinhola.db.models import Alert, IntervalConsumption, SupplyPoint
from portinhola.integrations import eredes_session
from portinhola.integrations.eredes_api import SessionExpiredError
from portinhola.jobs.eredes_sync import eredes_sync

KEY_COOKIES = [{"name": "s", "value": "v"}]


def _setup_sp(db) -> int:
    sp = SupplyPoint(utility="electricity", identifier="PT0002000000000000XX", name="Casa")
    db.add(sp)
    db.commit()
    return sp.id


def test_sync_without_cookies_raises_alert(app) -> None:
    with app.state.sessionmaker() as db:
        _setup_sp(db)
        log = eredes_sync(db)
        assert "not connected" in log
        alert = db.scalar(select(Alert).where(Alert.type == "eredes_not_connected"))
        assert alert is not None


def test_sync_happy_path_upserts(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))
    rows = [
        (datetime(2026, 7, 20, 10, 0, tzinfo=UTC), 0.25, "real"),
        (datetime(2026, 7, 20, 10, 15, tzinfo=UTC), 0.30, "real"),
    ]
    monkeypatch.setattr(
        "portinhola.jobs.eredes_sync.fetch_consumption",
        lambda cookies, cpe, date_from, date_to: rows,
    )
    with app.state.sessionmaker() as db:
        _setup_sp(db)
        from portinhola.core.secrets import load_or_create_app_key

        app_key = load_or_create_app_key(tmp_path)
        eredes_session.save_cookies(db, app_key, KEY_COOKIES)
        log = eredes_sync(db)
        assert "2 intervals" in log
        assert db.query(IntervalConsumption).count() == 2


def test_sync_expired_session_alerts_once(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))

    def boom(cookies, cpe, date_from, date_to):
        raise SessionExpiredError()

    monkeypatch.setattr("portinhola.jobs.eredes_sync.fetch_consumption", boom)
    notifications: list[str] = []
    monkeypatch.setattr(
        "portinhola.jobs.eredes_sync.notify_send",
        lambda db, title, body: notifications.append(title) or True,
    )
    with app.state.sessionmaker() as db:
        _setup_sp(db)
        from portinhola.core.secrets import load_or_create_app_key

        app_key = load_or_create_app_key(tmp_path)
        eredes_session.save_cookies(db, app_key, KEY_COOKIES)
        for _ in range(2):
            try:
                eredes_sync(db)
            except SessionExpiredError:
                pass
        alerts = db.query(Alert).filter(Alert.type == "eredes_session_expired").all()
        assert len(alerts) == 1
        assert len(notifications) == 2
