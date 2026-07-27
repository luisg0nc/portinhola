from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from portinhola.core.cycles import period_for

LISBON = ZoneInfo("Europe/Lisbon")


def _utc(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=LISBON).astimezone(UTC)


def test_simples_is_always_total() -> None:
    assert period_for(_utc(2026, 1, 15, 3, 0), "simples") == "total"
    assert period_for(_utc(2026, 7, 15, 19, 0), "simples") == "total"


def test_bi_horario_boundaries() -> None:
    assert period_for(_utc(2026, 1, 15, 21, 45), "bi") == "fora_vazio"
    assert period_for(_utc(2026, 1, 15, 22, 0), "bi") == "vazio"
    assert period_for(_utc(2026, 1, 15, 7, 45), "bi") == "vazio"
    assert period_for(_utc(2026, 1, 15, 8, 0), "bi") == "fora_vazio"


def test_tri_horario_winter() -> None:
    # winter legal time (January)
    assert period_for(_utc(2026, 1, 15, 9, 30), "tri") == "ponta"
    assert period_for(_utc(2026, 1, 15, 10, 30), "tri") == "cheias"
    assert period_for(_utc(2026, 1, 15, 18, 30), "tri") == "ponta"
    assert period_for(_utc(2026, 1, 15, 20, 30), "tri") == "cheias"
    assert period_for(_utc(2026, 1, 15, 23, 0), "tri") == "vazio"


def test_tri_horario_summer() -> None:
    # summer legal time (July)
    assert period_for(_utc(2026, 7, 15, 9, 30), "tri") == "cheias"
    assert period_for(_utc(2026, 7, 15, 11, 0), "tri") == "ponta"
    assert period_for(_utc(2026, 7, 15, 13, 0), "tri") == "cheias"
    assert period_for(_utc(2026, 7, 15, 20, 0), "tri") == "ponta"
    assert period_for(_utc(2026, 7, 15, 21, 30), "tri") == "cheias"


def test_periods_follow_legal_time_across_dst() -> None:
    # 21:45 local is fora_vazio on both sides of the March DST switch
    assert period_for(_utc(2026, 3, 28, 21, 45), "bi") == "fora_vazio"
    assert period_for(_utc(2026, 3, 29, 21, 45), "bi") == "fora_vazio"


def test_ciclo_semanal_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        period_for(_utc(2026, 1, 15, 9, 0), "bi", cycle="semanal")
