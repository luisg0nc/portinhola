"""ERSE BTN period mapping, ciclo diário, Portugal continental.

Tables and sources: tariffs/cycles/README.md. Periods follow legal (clock)
time — the winter/summer split tracks the DST switch automatically via
Europe/Lisbon localization.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

LISBON = ZoneInfo("Europe/Lisbon")

# (start_minute_of_day inclusive, end exclusive, period)
_TRI_WINTER = [
    (0, 8 * 60, "vazio"),
    (8 * 60, 9 * 60, "cheias"),
    (9 * 60, 10 * 60 + 30, "ponta"),
    (10 * 60 + 30, 18 * 60, "cheias"),
    (18 * 60, 20 * 60 + 30, "ponta"),
    (20 * 60 + 30, 22 * 60, "cheias"),
    (22 * 60, 24 * 60, "vazio"),
]
_TRI_SUMMER = [
    (0, 8 * 60, "vazio"),
    (8 * 60, 10 * 60 + 30, "cheias"),
    (10 * 60 + 30, 13 * 60, "ponta"),
    (13 * 60, 19 * 60 + 30, "cheias"),
    (19 * 60 + 30, 21 * 60, "ponta"),
    (21 * 60, 22 * 60, "cheias"),
    (22 * 60, 24 * 60, "vazio"),
]


def period_for(ts_utc: datetime, option: str, cycle: str = "diario") -> str:
    if cycle != "diario":
        raise NotImplementedError(
            "only ciclo diário is implemented; see tariffs/cycles/README.md"
        )
    if option == "simples":
        return "total"

    local = ts_utc.astimezone(LISBON)
    minute = local.hour * 60 + local.minute

    if option == "bi":
        return "vazio" if minute >= 22 * 60 or minute < 8 * 60 else "fora_vazio"

    if option == "tri":
        # Summer legal time == DST in effect (UTC offset +1 for Lisbon).
        table = _TRI_SUMMER if local.dst() else _TRI_WINTER
        for start, end, period in table:
            if start <= minute < end:
                return period
        raise AssertionError("minute outside day")  # pragma: no cover

    raise ValueError(f"unknown option: {option}")
