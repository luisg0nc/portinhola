from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from portinhola.db.models import Alert, IntervalConsumption, SupplyPoint
from portinhola.integrations import eredes_session
from portinhola.integrations.eredes_api import SessionExpiredError
from portinhola.jobs.eredes_sync import eredes_sync
from portinhola.jobs.registry import JobFailure


def _setup_sp(db) -> int:
    sp = SupplyPoint(utility="electricity", identifier="PT0002000000000000XX", name="Casa")
    db.add(sp)
    db.commit()
    return sp.id


def test_sync_without_session_fails_with_alert(app) -> None:
    with app.state.sessionmaker() as db:
        _setup_sp(db)
        with pytest.raises(JobFailure, match="not_connected"):
            eredes_sync(db)
        alert = db.scalar(select(Alert).where(Alert.type == "eredes_not_connected"))
        assert alert is not None


def test_sync_without_supply_point_fails_with_alert(app, monkeypatch, tmp_path) -> None:
    """A fresh install has a token but no CPE to query — that must be a
    loud, explained failure, not a silent 'skipped' success."""
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))
    with app.state.sessionmaker() as db:
        from portinhola.core.secrets import load_or_create_app_key

        app_key = load_or_create_app_key(tmp_path)
        eredes_session.save_token(db, app_key, "tok123")
        with pytest.raises(JobFailure, match="no_supply_point"):
            eredes_sync(db)
        alert = db.scalar(select(Alert).where(Alert.type == "eredes_no_supply_point"))
        assert alert is not None


def test_sync_happy_path_upserts(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))
    rows = [
        (datetime(2026, 7, 20, 10, 0, tzinfo=UTC), 0.25, "real"),
        (datetime(2026, 7, 20, 10, 15, tzinfo=UTC), 0.30, "real"),
    ]
    monkeypatch.setattr(
        "portinhola.jobs.eredes_sync.fetch_consumption",
        lambda db, app_key, cpe, date_from, date_to: rows,
    )
    with app.state.sessionmaker() as db:
        _setup_sp(db)
        from portinhola.core.secrets import load_or_create_app_key

        app_key = load_or_create_app_key(tmp_path)
        eredes_session.save_token(db, app_key, "tok123")
        log = eredes_sync(db)
        assert "2 intervals" in log
        assert db.query(IntervalConsumption).count() == 2


def test_sync_expired_session_alerts_once(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))

    def boom(db, app_key, cpe, date_from, date_to):
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
        eredes_session.save_token(db, app_key, "tok123")
        for _ in range(2):
            with pytest.raises(JobFailure, match="session_expired"):
                eredes_sync(db)
        alerts = db.query(Alert).filter(Alert.type == "eredes_session_expired").all()
        assert len(alerts) == 1
        assert len(notifications) == 2


def test_first_sync_walks_back_until_data_runs_out(app, monkeypatch, tmp_path) -> None:
    """First sync must discover the portal's real horizon, not assume 365d."""
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))
    from datetime import UTC, date, datetime, timedelta

    # Pretend the account holds ~75 days of history and nothing older.
    horizon = date(2026, 5, 1)
    asked: list[tuple[date, date]] = []

    def fake_fetch(db, app_key, cpe, date_from, date_to):
        asked.append((date_from, date_to))
        if date_to < horizon:
            return []  # portal has nothing this old
        start = max(date_from, horizon)
        out, day = [], start
        while day <= date_to:
            out.append((datetime(day.year, day.month, day.day, tzinfo=UTC), 0.1, "real"))
            day += timedelta(days=1)
        return out

    monkeypatch.setattr("portinhola.jobs.eredes_sync.fetch_consumption", fake_fetch)
    monkeypatch.setattr("portinhola.jobs.eredes_sync.utc_today", lambda: date(2026, 7, 15))

    with app.state.sessionmaker() as db:
        _setup_sp(db)
        from portinhola.core.secrets import load_or_create_app_key

        eredes_session.save_token(db, load_or_create_app_key(tmp_path), "tok123")
        log = eredes_sync(db)

    # It kept walking past a year's worth? No — it stopped when data ran out,
    # after seeing 2 consecutive empty windows beyond the horizon.
    assert len(asked) >= 4
    assert min(a[0] for a in asked) < horizon  # probed past the edge
    # Every stored day from the horizon onwards was captured.
    assert "intervals" in log
    with app.state.sessionmaker() as db:
        assert db.query(IntervalConsumption).count() == (date(2026, 7, 15) - horizon).days + 1


def test_incremental_sync_only_fetches_recent(app, monkeypatch, tmp_path) -> None:
    """With data present, sync must NOT re-pull all history."""
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))
    from datetime import UTC, date, datetime

    from portinhola.db.consumption_repo import upsert_intervals

    asked: list[tuple[date, date]] = []

    def fake_fetch(db, app_key, cpe, date_from, date_to):
        asked.append((date_from, date_to))
        # A real fetch never returns an empty list (it raises instead), and
        # an empty result now fails the job as "no_data".
        return [(datetime(2026, 7, 14, 10, 0, tzinfo=UTC), 0.2, "real")]

    monkeypatch.setattr("portinhola.jobs.eredes_sync.fetch_consumption", fake_fetch)
    monkeypatch.setattr("portinhola.jobs.eredes_sync.utc_today", lambda: date(2026, 7, 15))

    with app.state.sessionmaker() as db:
        sp_id = _setup_sp(db)
        upsert_intervals(
            db, sp_id, [(datetime(2026, 7, 13, 10, 0, tzinfo=UTC), 0.2, "eredes_scrape", "real")]
        )
        from portinhola.core.secrets import load_or_create_app_key

        eredes_session.save_token(db, load_or_create_app_key(tmp_path), "tok123")
        eredes_sync(db)

    assert len(asked) == 1  # single window, no walk-back
    assert asked[0][0] == date(2026, 7, 12)  # last stored day minus 1
