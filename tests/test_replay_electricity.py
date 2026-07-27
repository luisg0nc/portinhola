"""Golden test: the engine must reproduce the owner's real 2026-07 G9 bill.

Real electricity component (30 days, 2026-06-09..2026-07-08, 295 kWh,
4.6 kVA simples, prices printed on the bill):
  energy (incl. network access)  45.64 €  (200 kWh @6% VAT, 95 kWh @23%)
  potência                       10.48 €  (30 d × 0.3493)
  IEC                             0.29 €
  CAV                             2.81 €
  DGEG                            0.07 €
  subtotal                       59.29 €
  VAT                             7.90 €
  TOTAL                          67.19 €  (printed: "Faturação de Eletricidade")
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from portinhola.core.replay import replay_electricity
from portinhola.core.tariffs import load_tariffs, load_taxes

TARIFFS = {t.id: t for t in load_tariffs()}
TAXES = load_taxes()


def _flat_consumption(start: date, days: int, total_kwh: float):
    slots = days * 96
    per_slot = total_kwh / slots
    first = datetime(start.year, start.month, start.day, tzinfo=UTC)
    return [(first + timedelta(minutes=15 * i), per_slot) for i in range(slots)]


def test_golden_g9_july_bill() -> None:
    consumption = _flat_consumption(date(2026, 6, 9), 30, 295.0)
    sim = replay_electricity(
        consumption,
        TARIFFS["g9-simples"],
        TAXES,
        kva=4.6,
        option="simples",
        period_start=date(2026, 6, 9),
        period_end=date(2026, 7, 8),
    )
    by_label = {line.label: line for line in sim.lines}
    assert abs(by_label["energy_reduced"].amount_cents - 3094) <= 1
    assert abs(by_label["energy_standard"].amount_cents - 1470) <= 1
    assert abs(by_label["power"].amount_cents - 1048) <= 1
    assert abs(by_label["iec"].amount_cents - 29) <= 1
    assert abs(by_label["cav"].amount_cents - 281) <= 1
    assert abs(by_label["dgeg"].amount_cents - 7) <= 1
    assert abs(sim.subtotal_cents - 5929) <= 2
    assert abs(sim.vat_cents - 790) <= 3
    assert abs(sim.total_cents - 6719) <= 3
    assert sim.energy_kwh == pytest.approx(295.0)
    assert sim.days == 30


def test_bi_horario_splits_periods() -> None:
    import copy

    tariff = copy.deepcopy(TARIFFS["g9-simples"])
    tariff.electricity.energy_eur_kwh["bi"] = {"vazio": 0.10, "fora_vazio": 0.20}
    # one full winter day: 40 slots in vazio (22-08h = 10h) vs 56 fora
    consumption = _flat_consumption(date(2026, 1, 10), 1, 9.6)  # 0.1 kWh/slot
    sim = replay_electricity(
        consumption,
        tariff,
        TAXES,
        kva=4.6,
        option="bi",
        period_start=date(2026, 1, 10),
        period_end=date(2026, 1, 10),
    )
    # vazio: 10h = 40 slots × 0.1 = 4.0 kWh × 0.10 = 0.40; fora: 5.6 × 0.20 = 1.12
    energy_total = sum(
        line.amount_cents for line in sim.lines if line.label.startswith("energy")
    )
    assert abs(energy_total - 152) <= 1


def test_vat_tranche_prorated_for_short_period() -> None:
    consumption = _flat_consumption(date(2026, 6, 9), 15, 295.0)
    sim = replay_electricity(
        consumption,
        TARIFFS["g9-simples"],
        TAXES,
        kva=4.6,
        option="simples",
        period_start=date(2026, 6, 9),
        period_end=date(2026, 6, 23),
    )
    by_label = {line.label: line for line in sim.lines}
    # 15 days → only 100 kWh at reduced rate
    assert abs(by_label["energy_reduced"].amount_cents - round(100 * 15.47)) <= 1
