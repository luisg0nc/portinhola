import subprocess
import sys
import threading
from datetime import UTC, datetime

from fastapi import FastAPI

# A full E-Redes backfill is many chunked portal calls with `wait: true`,
# each slow — far beyond the default watchdog. Progress persists per
# window, so even the long ceiling only bounds runaway processes.
JOB_TIMEOUTS = {"eredes_sync": 3600}


def spawn_job(job_type: str, timeout: int | None = None) -> None:
    """Run a job as a short-lived subprocess with a hard timeout."""
    if timeout is None:
        timeout = JOB_TIMEOUTS.get(job_type, 600)
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

    scheduler = BackgroundScheduler()
    # NOTE: no scheduled eredes_sync. The portal's `aat` session token lives
    # only ~91 minutes and cannot be renewed server-side (minting a new one
    # is gated by invisible reCAPTCHA), so a daily cron would almost always
    # find it expired and do nothing but raise alerts. E-Redes syncs run on
    # demand instead: immediately when a token is imported, and via the
    # "Sync now" button.
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
