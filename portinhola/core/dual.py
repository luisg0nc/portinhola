"""Combine per-fuel replay results into a dual-bundle total.

Percentage discounts scale each fuel's energy-labelled lines while
preserving their VAT split; the flat monthly credit is applied at the
standard VAT rate. Discounts marked with `promo_months` are a first-year
phase: they are excluded from the steady-state total and pro-rated into
the first-year total.
"""

from pydantic import BaseModel

from portinhola.core.promos import DAYS_PER_MONTH, discount_on_lines, promo_fraction
from portinhola.core.replay import BillSim, _cents
from portinhola.core.tariffs import DualBundle, TaxConfig


class DualResult(BaseModel):
    elec_total_cents: int
    gas_total_cents: int
    discount_cents: int  # steady-state discount (negative or zero)
    total_cents: int  # steady-state combined total
    first_year_total_cents: int


def _bundle_discount(elec: BillSim, gas: BillSim, bundle: DualBundle, taxes: TaxConfig) -> int:
    discount = discount_on_lines(elec, bundle.discounts.electricity_energy_pct, ("energy",))
    discount += discount_on_lines(gas, bundle.discounts.gas_energy_pct, ("energy",))
    if bundle.discounts.fixed_eur_month > 0:
        months = max(elec.days, gas.days) / DAYS_PER_MONTH
        net = _cents(bundle.discounts.fixed_eur_month * months)
        discount += net + _cents(net / 100 * taxes.vat.standard_rate / 100)
    return discount


def combine(
    elec: BillSim, gas: BillSim, bundle: DualBundle | None, taxes: TaxConfig
) -> DualResult:
    plain = elec.total_cents + gas.total_cents
    steady_discount = 0
    first_year_discount = 0
    if bundle is not None:
        full = _bundle_discount(elec, gas, bundle, taxes)
        if bundle.discounts.promo_months is None:
            steady_discount = full
            first_year_discount = full
        else:
            fraction = promo_fraction(
                bundle.discounts.promo_months, max(elec.days, gas.days)
            )
            first_year_discount = round(full * fraction)
    return DualResult(
        elec_total_cents=elec.total_cents,
        gas_total_cents=gas.total_cents,
        discount_cents=-steady_discount,
        total_cents=plain - steady_discount,
        first_year_total_cents=plain - first_year_discount,
    )
