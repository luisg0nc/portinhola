import time

from sqlalchemy import select

from portinhola.db.models import Job


def test_heartbeat_job_writes_success_row(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))
    from portinhola.jobs.run import main

    assert main("heartbeat") == 0
    with app.state.sessionmaker() as db:
        job = db.scalar(select(Job).where(Job.type == "heartbeat"))
        assert job is not None
        assert job.status == "success"
        assert job.log == "ok"
        assert job.finished_at is not None


def test_failing_job_writes_failed_row(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))
    from portinhola.jobs.registry import job
    from portinhola.jobs.run import main

    @job("always_fails")
    def always_fails(db) -> str:
        raise RuntimeError("boom")

    assert main("always_fails") == 1
    with app.state.sessionmaker() as db_session:
        row = db_session.scalar(select(Job).where(Job.type == "always_fails"))
        assert row.status == "failed"
        assert "boom" in row.error


def test_job_failure_stores_clean_code_not_traceback(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))
    from portinhola.jobs.registry import JobFailure, job
    from portinhola.jobs.run import main

    @job("fails_cleanly")
    def fails_cleanly(db) -> str:
        raise JobFailure("some_code")

    assert main("fails_cleanly") == 1
    with app.state.sessionmaker() as db_session:
        row = db_session.scalar(select(Job).where(Job.type == "fails_cleanly"))
        assert row.status == "failed"
        assert row.error == "some_code"


def test_unknown_job_type_exits_nonzero(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))
    from portinhola.jobs.run import main

    assert main("nope") == 2


def test_spawn_job_runs_heartbeat_subprocess(app, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PORTINHOLA_DATA_DIR", str(tmp_path))
    from portinhola.core.scheduler import spawn_job

    spawn_job("heartbeat", timeout=30)
    deadline = time.time() + 20
    found = None
    while time.time() < deadline:
        with app.state.sessionmaker() as db:
            found = db.scalar(
                select(Job).where(Job.type == "heartbeat", Job.status == "success")
            )
        if found is not None:
            break
        time.sleep(0.3)
    assert found is not None
