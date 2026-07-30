from datetime import date

import pytest

from portinhola.core.dual import combine
from portinhola.core.replay import BillLineSim, BillSim
from portinhola.core.tariffs import (
    DualBundle,
    DualDiscounts,
    TariffLoadError,
    load_dual_bundles,
    load_tariffs,
    load_taxes,
)


def _sim(lines: list[tuple[str, int, int]], days: int = 365) -> BillSim:
    sim_lines = [
        BillLineSim(label=label, amount_cents=net, vat_rate=vat) for label, net, vat in lines
    ]
    subtotal = sum(line.amount_cents for line in sim_lines)
    vat = sum(round(line.amount_cents * line.vat_rate / 100) for line in sim_lines)
    return BillSim(
        lines=sim_lines,
        subtotal_cents=subtotal,
        vat_cents=vat,
        total_cents=subtotal + vat,
        energy_kwh=0.0,
        days=days,
    )


def _bundle(**discounts) -> DualBundle:
    return DualBundle(
        id="x",
        supplier="X",
        name="X Dual",
        electricity_tariff="e",
        gas_tariff="g",
        valid_from=date(2026, 1, 1),
        source_url="https://example.com",
        retrieved=date(2026, 7, 30),
        discounts=DualDiscounts(**discounts),
    )


def test_combine_without_bundle_is_plain_sum() -> None:
    elec = _sim([("energy", 10000, 23)])
    gas = _sim([("energy", 5000, 23)])
    result = combine(elec, gas, None, load_taxes())
    assert result.discount_cents == 0
    assert result.total_cents == elec.total_cents + gas.total_cents


def test_combine_pct_discount_respects_vat_split() -> None:
    # 100.00 at 6% and 100.00 at 23% energy; 10% discount saves
    # 10.00+0.60 and 10.00+2.30 = 22.90 total.
    elec = _sim([("energy_reduced", 10000, 6), ("energy", 10000, 23), ("power", 5000, 23)])
    gas = _sim([("energy", 0, 23)])
    result = combine(elec, gas, _bundle(electricity_energy_pct=10.0), load_taxes())
    assert result.discount_cents == -2290
    assert result.total_cents == elec.total_cents + gas.total_cents - 2290


def test_combine_flat_monthly_credit() -> None:
    # 1.02 €/month over 365.25 days = 12 months → 12.24 net + 23% VAT.
    elec = _sim([("energy", 10000, 23)], days=366)
    gas = _sim([("energy", 5000, 23)], days=100)
    result = combine(elec, gas, _bundle(fixed_eur_month=1.02), load_taxes())
    months = 366 / (365.25 / 12)
    net = round(1.02 * months * 100)
    expected = net + round(net * 0.23)
    assert result.discount_cents == -expected


def test_load_dual_bundles_validates_references(tmp_path) -> None:
    tariffs = load_tariffs()
    bundles = load_dual_bundles(tariffs)
    assert any(b.id == "edp" for b in bundles)
    edp = next(b for b in bundles if b.id == "edp")
    assert edp.discounts.electricity_energy_pct == 15.0

    bad = tmp_path / "dual"
    bad.mkdir()
    (bad / "broken.yaml").write_text(
        "supplier: X\nname: X\nelectricity_tariff: nope\ngas_tariff: g9-gas\n"
        "valid_from: 2026-01-01\nsource_url: https://x\nretrieved: 2026-07-30\n"
    )
    with pytest.raises(TariffLoadError, match="nope"):
        load_dual_bundles(tariffs, base_dir=tmp_path)
