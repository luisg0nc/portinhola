"""Combine per-fuel replay results into a dual-bundle total.

Percentage discounts scale each fuel's energy-labelled lines while
preserving their VAT split (a discount on a 6%-VAT tranche saves 6%-VAT
money); the flat monthly credit is applied at the standard VAT rate.
"""

from pydantic import BaseModel

from portinhola.core.replay import BillSim, _cents
from portinhola.core.tariffs import DualBundle, TaxConfig

DAYS_PER_MONTH = 365.25 / 12


class DualResult(BaseModel):
    elec_total_cents: int
    gas_total_cents: int
    discount_cents: int  # negative or zero: money off, VAT included
    total_cents: int


def _energy_discount_cents(sim: BillSim, pct: float) -> int:
    """VAT-inclusive saving from scaling energy lines down by pct."""
    if pct <= 0:
        return 0
    saved = 0
    for line in sim.lines:
        if not line.label.startswith("energy"):
            continue
        net = round(line.amount_cents * pct / 100)
        saved += net + _cents(net / 100 * line.vat_rate / 100)
    return saved


def combine(
    elec: BillSim, gas: BillSim, bundle: DualBundle | None, taxes: TaxConfig
) -> DualResult:
    discount = 0
    if bundle is not None:
        discount += _energy_discount_cents(elec, bundle.discounts.electricity_energy_pct)
        discount += _energy_discount_cents(gas, bundle.discounts.gas_energy_pct)
        if bundle.discounts.fixed_eur_month > 0:
            months = max(elec.days, gas.days) / DAYS_PER_MONTH
            net = _cents(bundle.discounts.fixed_eur_month * months)
            discount += net + _cents(net / 100 * taxes.vat.standard_rate / 100)
    return DualResult(
        elec_total_cents=elec.total_cents,
        gas_total_cents=gas.total_cents,
        discount_cents=-discount,
        total_cents=elec.total_cents + gas.total_cents - discount,
    )
