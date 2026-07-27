"""Subprocess entrypoint: python -m portinhola.jobs.run <job_type>.

Creates its own engine/session from Config, records a Job row, runs the
registered job function, and exits. Exit codes: 0 success, 1 job failure,
2 unknown job type.
"""

import sys
import traceback
from datetime import UTC, datetime

from sqlalchemy.orm import sessionmaker

from portinhola.config import Config
from portinhola.db.base import make_engine
from portinhola.db.models import Job
from portinhola.jobs import eredes_sync as _eredes_sync  # noqa: F401  (registers job)
from portinhola.jobs.registry import JOB_TYPES


def main(job_type: str) -> int:
    func = JOB_TYPES.get(job_type)
    if func is None:
        return 2

    config = Config()
    engine = make_engine(config.database_url)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as db:
        job_row = Job(type=job_type, status="running", started_at=datetime.now(UTC))
        db.add(job_row)
        db.commit()
        try:
            log = func(db)
        except Exception:  # noqa: BLE001 - job failures must be recorded, never crash silently
            job_row.status = "failed"
            job_row.error = traceback.format_exc(limit=5)
            job_row.finished_at = datetime.now(UTC)
            db.commit()
            return 1
        job_row.status = "success"
        job_row.log = log
        job_row.finished_at = datetime.now(UTC)
        db.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
