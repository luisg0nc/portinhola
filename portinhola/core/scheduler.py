import subprocess
import sys
import threading
from datetime import UTC, datetime

from fastapi import FastAPI


def spawn_job(job_type: str, timeout: int = 600) -> None:
    """Run a job as a short-lived subprocess with a hard timeout."""
    process = subprocess.Popen(
        [sys.executable, "-m", "portinhola.jobs.run", job_type],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    def watchdog() -> None:
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            _mark_timed_out(job_type)

    threading.Thread(target=watchdog, daemon=True).start()


def _mark_timed_out(job_type: str) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    from portinhola.config import Config
    from portinhola.db.base import make_engine
    from portinhola.db.models import Job

    engine = make_engine(Config().database_url)
    with sessionmaker(bind=engine)() as db:
        job = db.scalar(
            select(Job)
            .where(Job.type == job_type, Job.status == "running")
            .order_by(Job.started_at.desc())
        )
        if job is not None:
            job.status = "timeout"
            job.finished_at = datetime.now(UTC)
            db.commit()


def setup_scheduler(app: FastAPI) -> None:
    from apscheduler.schedulers.background import BackgroundScheduler

    from portinhola.db.settings_repo import get_setting

    scheduler = BackgroundScheduler()
    with app.state.sessionmaker() as db:
        sync_time = get_setting(db, "eredes_sync_time") or "07:00"
    hour, _, minute = sync_time.partition(":")
    scheduler.add_job(
        spawn_job,
        "cron",
        args=["eredes_sync"],
        hour=int(hour),
        minute=int(minute or 0),
        id="eredes_sync",
    )
    scheduler.add_job(
        spawn_job,
        "cron",
        args=["reading_reminders"],
        hour=9,
        minute=0,
        id="reading_reminders",
    )
    scheduler.start()
    app.state.scheduler = scheduler
