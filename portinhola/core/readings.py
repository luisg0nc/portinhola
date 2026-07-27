from sqlalchemy import select
from sqlalchemy.orm import Session

from portinhola.db.models import Reading

REGISTERS_BY_UTILITY: dict[str, list[str]] = {
    "electricity": ["Vazio", "Cheias", "Ponta"],
    "gas": ["Total"],
    "water": ["Total"],
}


def latest_readings(db: Session, supply_point_id: int) -> dict[str, Reading]:
    latest: dict[str, Reading] = {}
    rows = db.scalars(
        select(Reading)
        .where(Reading.supply_point_id == supply_point_id)
        .order_by(Reading.taken_at)
    )
    for reading in rows:
        latest[reading.register] = reading
    return latest
