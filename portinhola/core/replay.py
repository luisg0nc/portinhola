"""Counterfactual bill computation: replay real consumption against a
tariff's full price vector, then add levies and per-component VAT.

This is the calculation that decides bi-horário vs simples correctly —
estimates from monthly totals (à la Poupa Energia) cannot see the curve.
"""

from collections import defaultdict
from datetime import date, datetime
from math import floor

from pydantic import BaseModel

from portinhola.core.cycles import period_for
from portinhola.core.tariffs import Tariff, TaxConfig

CAV_EUR_DAY_FACTOR = 12 / 365.25  # 2.85 € × 12 months / 365.25 days (as billed)

PERIOD_LABELS = {"total": "energy", "vazio": "energy_vazio", "fora_vazio": "energy_fora_vazio",
                 "cheias": "energy_cheias", "ponta": "energy_ponta"}


class BillLineSim(BaseModel):
    label: str
    amount_cents: int
    vat_rate: int


class BillSim(BaseModel):
    lines: list[BillLineSim]
    subtotal_cents: int
    vat_cents: int
    total_cents: int
    energy_kwh: float
    days: int


def _cents(eur: float) -> int:
    return int(floor(eur * 100 + 0.5))


def _finalize(lines: list[BillLineSim], energy_kwh: float, days: int) -> BillSim:
    subtotal = sum(line.amount_cents for line in lines)
    vat = sum(_cents(line.amount_cents / 100 * line.vat_rate / 100) for line in lines)
    return BillSim(
        lines=lines,
        subtotal_cents=subtotal,
        vat_cents=vat,
        total_cents=subtotal + vat,
        energy_kwh=round(energy_kwh, 3),
        days=days,
    )


def _nearest_power_price(power_eur_day: dict[str, float], kva: float) -> float:
    if str(kva) in power_eur_day:
        return power_eur_day[str(kva)]
    best = min(power_eur_day, key=lambda k: abs(float(k) - kva))
    return power_eur_day[best]


def replay_electricity(
    consumption: list[tuple[datetime, float]],
    tariff: Tariff,
    taxes: TaxConfig,
    kva: float,
    option: str,
    period_start: date,
    period_end: date,
) -> BillSim:
    if tariff.electricity is None or option not in tariff.electricity.energy_eur_kwh:
        raise ValueError(f"tariff {tariff.id} has no prices for option {option}")
    days = (period_end - period_start).days + 1
    prices = tariff.electricity.energy_eur_kwh[option]

    kwh_by_period: dict[str, float] = defaultdict(float)
    for ts, kwh in consumption:
        kwh_by_period[period_for(ts, option)] += kwh
    total_kwh = sum(kwh_by_period.values())

    energy_cost_eur = sum(kwh * prices[period] for period, kwh in kwh_by_period.items())

    # VAT tranche: first N kWh per 30 days at the reduced rate, applied to
    # the aggregate energy cost proportionally (bills bill the tranche at
    # the same €/kWh, only the VAT differs).
    reduced_kwh = min(total_kwh, taxes.vat.energy_reduced_kwh_per_30d * days / 30)
    reduced_fraction = (reduced_kwh / total_kwh) if total_kwh > 0 else 0.0

    lines: list[BillLineSim] = [
        BillLineSim(
            label="energy_reduced",
            amount_cents=_cents(energy_cost_eur * reduced_fraction),
            vat_rate=taxes.vat.reduced_rate,
        ),
        BillLineSim(
            label="energy_standard",
            amount_cents=_cents(energy_cost_eur * (1 - reduced_fraction)),
            vat_rate=taxes.vat.standard_rate,
        ),
        BillLineSim(
            label="power",
            amount_cents=_cents(
                _nearest_power_price(tariff.electricity.power_eur_day, kva) * days
            ),
            vat_rate=(
                taxes.vat.reduced_rate
                if kva <= taxes.vat.power_reduced_max_kva
                else taxes.vat.standard_rate
            ),
        ),
        BillLineSim(
            label="iec",
            amount_cents=_cents(total_kwh * taxes.iec_elec_eur_kwh),
            vat_rate=taxes.vat.standard_rate,
        ),
        BillLineSim(
            label="cav",
            amount_cents=_cents(taxes.cav_eur_month * CAV_EUR_DAY_FACTOR * days),
            vat_rate=taxes.vat.reduced_rate,
        ),
        BillLineSim(
            label="dgeg",
            amount_cents=_cents(taxes.dgeg_eur_month * days / 30),
            vat_rate=taxes.vat.standard_rate,
        ),
    ]
    return _finalize(lines, total_kwh, days)


def replay_gas(
    kwh: float,
    days: int,
    tariff: Tariff,
    taxes: TaxConfig,
    tier: str,
    municipality: str | None = None,
) -> BillSim:
    if tariff.gas is None or tier not in tariff.gas.tiers:
        raise ValueError(f"tariff {tariff.id} has no gas tier {tier}")
    gas_tier = tariff.gas.tiers[tier]
    tos = taxes.tos_gas.get(municipality or taxes.default_municipality)

    fixed_eur = gas_tier.fixed_eur_day * days
    fixed_reduced = fixed_eur * gas_tier.fixed_reduced_share
    lines: list[BillLineSim] = [
        BillLineSim(
            label="energy",
            amount_cents=_cents(kwh * gas_tier.energy_eur_kwh),
            vat_rate=taxes.vat.standard_rate,
        ),
        BillLineSim(
            label="fixed_standard",
            amount_cents=_cents(fixed_eur - fixed_reduced),
            vat_rate=taxes.vat.standard_rate,
        ),
        BillLineSim(
            label="fixed_reduced",
            amount_cents=_cents(fixed_reduced),
            vat_rate=taxes.vat.reduced_rate,
        ),
        BillLineSim(
            label="iec",
            amount_cents=_cents(kwh * taxes.iec_gas_eur_kwh),
            vat_rate=taxes.vat.standard_rate,
        ),
    ]
    if tos is not None:
        lines.append(
            BillLineSim(
                label="tos",
                amount_cents=_cents(kwh * tos.eur_kwh + days * tos.eur_day),
                vat_rate=taxes.vat.standard_rate,
            )
        )
    return _finalize(lines, kwh, days)
