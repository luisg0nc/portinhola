
import pytest

from portinhola.core.promos import first_year_total, promo_fraction
from portinhola.core.tariffs import Promo, TariffLoadError, load_tariffs
from tests.test_dual import _sim


def _promo(**kwargs) -> Promo:
    return Promo(**kwargs)


def test_first_year_prorates_promo_over_window() -> None:
    # 12-month window, 3-month promo of 10% off 100.00€ energy @23% VAT:
    # full saving 12.30, pro-rated 3/12 → ~3.07 off.
    sim = _sim([("energy", 10000, 23)], days=365)
    promo = _promo(energy_pct=10.0, months=3)
    fraction = promo_fraction(3, 365)
    assert abs(fraction - (3 * 365.25 / 12) / 365) < 0.01
    expected = sim.total_cents - round(1230 * fraction)
    assert first_year_total(sim, promo) == expected


def test_promo_longer_than_window_caps_at_window() -> None:
    sim = _sim([("energy", 10000, 23)], days=90)
    promo = _promo(energy_pct=10.0, months=12)
    assert first_year_total(sim, promo) == sim.total_cents - 1230


def test_fixed_pct_promo_hits_power_lines() -> None:
    sim = _sim([("energy", 10000, 23), ("power", 5000, 23)], days=365)
    promo = _promo(fixed_pct=30.0, months=12)
    # 30% of 50.00 = 15.00 net + 3.45 VAT, promo covers full window
    assert first_year_total(sim, promo) == sim.total_cents - 1845


def test_no_promo_is_identity() -> None:
    sim = _sim([("energy", 10000, 23)], days=365)
    assert first_year_total(sim, None) == sim.total_cents


def test_power_floor_validation_rejects_fabricated_ladders(tmp_path) -> None:
    """Any potência below the regulated access floor (0.0498 €/day/kVA) is
    fabricated data and must fail loudly at load time."""
    elec_dir = tmp_path / "electricity"
    elec_dir.mkdir()
    (elec_dir / "bogus.yaml").write_text(
        "supplier: X\nname: X\nutility: electricity\nvalid_from: 2026-01-01\n"
        "source_url: https://x\nretrieved: 2026-07-30\n"
        "electricity:\n  power_eur_day:\n    \"4.6\": 0.15\n"
        "  energy_eur_kwh:\n    simples:\n      total: 0.14\n"
    )
    with pytest.raises(TariffLoadError, match="below the regulated access floor"):
        load_tariffs(base_dir=tmp_path)


def test_all_seeded_ladders_pass_the_floor() -> None:
    tariffs = load_tariffs()
    edp = next(t for t in tariffs if t.id == "edp-simples")
    assert edp.promo is not None and edp.promo.months == 12
