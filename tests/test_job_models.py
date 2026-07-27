from datetime import UTC, datetime

from portinhola.core.alerts import raise_alert
from portinhola.db.models import Alert, Job


def test_job_lifecycle(app) -> None:
    with app.state.sessionmaker() as db:
        job = Job(type="heartbeat", status="running", started_at=datetime.now(UTC))
        db.add(job)
        db.commit()
        job.status = "success"
        job.finished_at = datetime.now(UTC)
        job.log = "ok"
        db.commit()
        assert db.get(Job, job.id).status == "success"


def test_alert_dedup_updates_instead_of_duplicating(app) -> None:
    with app.state.sessionmaker() as db:
        raise_alert(db, "eredes_session_expired", "expired at 10:00", dedup_key="eredes_expired")
        raise_alert(db, "eredes_session_expired", "expired at 11:00", dedup_key="eredes_expired")
        alerts = db.query(Alert).all()
        assert len(alerts) == 1
        assert alerts[0].message == "expired at 11:00"
        assert alerts[0].read is False


def test_alert_without_dedup_inserts_each_time(app) -> None:
    with app.state.sessionmaker() as db:
        raise_alert(db, "job_failed", "one")
        raise_alert(db, "job_failed", "two")
        assert db.query(Alert).count() == 2
