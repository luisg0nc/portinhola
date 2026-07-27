from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.core.scheduler import spawn_job
from portinhola.db.models import Job
from portinhola.jobs.registry import JOB_TYPES

router = APIRouter(dependencies=[Depends(require_auth)])


class JobOut(BaseModel):
    id: int
    type: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    log: str
    error: str | None

    model_config = {"from_attributes": True}


@router.get("")
def list_jobs(db: Session = Depends(get_db)) -> list[JobOut]:
    rows = db.scalars(select(Job).order_by(Job.started_at.desc(), Job.id.desc()).limit(50))
    return [JobOut.model_validate(row) for row in rows]


@router.post("/{job_type}/run", status_code=202)
def run_job(job_type: str) -> dict[str, str]:
    if job_type not in JOB_TYPES:
        raise HTTPException(status_code=404, detail="unknown_job_type")
    spawn_job(job_type)
    return {"status": "spawned"}
