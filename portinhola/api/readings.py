from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.api.deps import get_db, require_auth
from portinhola.core.readings import REGISTERS_BY_UTILITY, latest_readings
from portinhola.db.models import Reading, SupplyPoint

router = APIRouter(dependencies=[Depends(require_auth)])


class ReadingIn(BaseModel):
    supply_point_id: int
    values: dict[str, float]
    taken_at: datetime | None = None
    allow_decrease: bool = False
    note: str = ""


class ReadingOut(BaseModel):
    id: int
    supply_point_id: int
    register: str
    value: float
    taken_at: datetime
    submission_status: str
    note: str

    model_config = {"from_attributes": True}


class ReadingPatch(BaseModel):
    submission_status: str | None = None


@router.post("", status_code=201)
def create_readings(body: ReadingIn, db: Session = Depends(get_db)) -> list[ReadingOut]:
    sp = db.get(SupplyPoint, body.supply_point_id)
    if sp is None:
        raise HTTPException(status_code=404, detail="supply_point_not_found")
    valid_registers = REGISTERS_BY_UTILITY[sp.utility]
    for register in body.values:
        if register not in valid_registers:
            raise HTTPException(
                status_code=422, detail={"error": "unknown_register", "register": register}
            )

    latest = latest_readings(db, sp.id)
    if not body.allow_decrease:
        for register, value in body.values.items():
            previous = latest.get(register)
            if previous is not None and value < previous.value:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "value_decreased",
                        "register": register,
                        "previous": previous.value,
                    },
                )

    taken_at = body.taken_at or datetime.now(UTC)
    created = []
    for register, value in body.values.items():
        reading = Reading(
            supply_point_id=sp.id,
            register=register,
            value=value,
            taken_at=taken_at,
            note=body.note,
        )
        db.add(reading)
        created.append(reading)
    db.commit()
    return [ReadingOut.model_validate(r) for r in created]


@router.get("")
def list_readings(supply_point_id: int, db: Session = Depends(get_db)) -> list[ReadingOut]:
    rows = db.scalars(
        select(Reading)
        .where(Reading.supply_point_id == supply_point_id)
        .order_by(Reading.taken_at.desc(), Reading.id.desc())
    )
    return [ReadingOut.model_validate(r) for r in rows]


@router.get("/latest")
def latest(supply_point_id: int, db: Session = Depends(get_db)) -> dict[str, ReadingOut]:
    return {
        register: ReadingOut.model_validate(reading)
        for register, reading in latest_readings(db, supply_point_id).items()
    }


@router.patch("/{reading_id}")
def patch_reading(
    reading_id: int, body: ReadingPatch, db: Session = Depends(get_db)
) -> ReadingOut:
    reading = db.get(Reading, reading_id)
    if reading is None:
        raise HTTPException(status_code=404, detail="reading_not_found")
    if body.submission_status is not None:
        reading.submission_status = body.submission_status
    db.commit()
    return ReadingOut.model_validate(reading)


@router.delete("/{reading_id}", status_code=204)
def delete_reading(reading_id: int, db: Session = Depends(get_db)) -> None:
    reading = db.get(Reading, reading_id)
    if reading is None:
        raise HTTPException(status_code=404, detail="reading_not_found")
    db.delete(reading)
    db.commit()
