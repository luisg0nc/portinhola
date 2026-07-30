"""Promotional-phase math shared by the per-fuel and dual calculators.

Discounts scale a sim's matching breakdown lines while preserving each
line's VAT rate, and a promo limited to N months is pro-rated over the
replay window (season-neutral: a new customer's promo start date is
arbitrary, so we don't pretend to know which months it covers).
"""

from portinhola.core.replay import BillSim, _cents
from portinhola.core.tariffs import Promo

DAYS_PER_MONTH = 365.25 / 12


def discount_on_lines(sim: BillSim, pct: float, prefixes: tuple[str, ...]) -> int:
    """VAT-inclusive saving from scaling matching lines down by pct."""
    if pct <= 0:
        return 0
    saved = 0
    for line in sim.lines:
        if not line.label.startswith(prefixes):
            continue
        net = round(line.amount_cents * pct / 100)
        saved += net + _cents(net / 100 * line.vat_rate / 100)
    return saved


def promo_fraction(months: int | None, window_days: int) -> float:
    """Share of the replay window covered by an N-month promo."""
    if months is None or window_days <= 0:
        return 1.0
    return min(months * DAYS_PER_MONTH, window_days) / window_days


def first_year_total(sim: BillSim, promo: Promo | None) -> int:
    """Window total as a new customer: promo phase pro-rated in."""
    if promo is None:
        return sim.total_cents
    fraction = promo_fraction(promo.months, sim.days)
    saving = discount_on_lines(sim, promo.energy_pct, ("energy",))
    saving += discount_on_lines(sim, promo.fixed_pct, ("power", "fixed"))
    return sim.total_cents - round(saving * fraction)
