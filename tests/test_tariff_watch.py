from datetime import date
from pathlib import Path

import pytest

from tools.tariff_watch.apply import apply_updates
from tools.tariff_watch.base import ParseFailed
from tools.tariff_watch.parsers import endesa, galp, goldenergy, regulated_gas
from tools.tariff_watch.watch import price_fingerprint

FIXDIR = Path(__file__).parent / "fixtures" / "tariff_watch"


def test_galp_parser_extracts_official_table() -> None:
    result = galp.parse((FIXDIR / "galp-residencial.pdf").read_bytes())
    elec = result["electricity/galp-simples.yaml"]
    assert elec["power:4.6"] == 0.3730
    assert elec["simples_total"] == 0.1561
    assert elec["bi_vazio"] == 0.1300
    gas = result["gas/galp-gas.yaml"]
    assert gas == {
        "tier1_fixed": 0.0937,
        "tier1_energy": 0.0991,
        "tier2_fixed": 0.1648,
        "tier2_energy": 0.1000,
    }


def test_endesa_parser_reads_discounted_columns_and_zipped_gas_rows() -> None:
    result = endesa.parse((FIXDIR / "endesa-digital.pdf").read_bytes())
    assert result["electricity/endesa-simples.yaml"]["power:4.6"] == 0.4584
    assert result["electricity/endesa-simples.yaml"]["simples_total"] == 0.1399
    assert result["electricity/endesa-bi.yaml"]["power:4.6"] == 0.4076
    assert result["electricity/endesa-bi.yaml"]["bi_vazio"] == 0.1191
    assert result["gas/endesa-gas.yaml"]["tier2_fixed"] == 0.2372


def test_goldenergy_parser_adds_social_surcharge() -> None:
    result = goldenergy.parse((FIXDIR / "goldenergy-precos.html").read_bytes())
    elec = result["electricity/goldenergy-simples.yaml"]
    assert elec["power:4.6"] == 0.4499
    assert elec["simples_total"] == pytest.approx(0.1399 + 0.0020666, abs=1e-4)
    gas = result["gas/goldenergy-gas.yaml"]
    assert gas["tier1_fixed"] == 0.0541
    assert gas["tier2_energy"] == 0.1275


def test_regulated_gas_parser() -> None:
    result = regulated_gas.parse((FIXDIR / "tf-regulada-gas.html").read_bytes())
    assert result["gas/su-gas.yaml"] == {
        "tier1_fixed": 0.0897,
        "tier1_energy": 0.0647,
        "tier2_fixed": 0.1298,
        "tier2_energy": 0.0601,
    }


def test_parsers_fail_loudly_on_layout_drift() -> None:
    with pytest.raises(ParseFailed):
        galp.parse(b"%PDF-1.4 not really a price table")


SAMPLE_YAML = """supplier: X
retrieved: 2026-01-01
electricity:
  power_eur_day:
    "4.6": 0.25
gas:
  tiers:
    "1":
      fixed_eur_day: 0.10
      energy_eur_kwh: 0.11
    "2":
      fixed_eur_day: 0.20
      energy_eur_kwh: 0.21
"""


def test_apply_updates_patches_values_and_retrieved(tmp_path) -> None:
    path = tmp_path / "x.yaml"
    path.write_text(SAMPLE_YAML)
    changed = apply_updates(
        path, {"power:4.6": 0.4584, "tier2_energy": 0.0830}, date(2026, 7, 30)
    )
    assert changed
    text = path.read_text()
    assert '"4.6": 0.4584' in text
    assert "energy_eur_kwh: 0.11" in text  # tier 1 untouched
    assert "energy_eur_kwh: 0.083" in text  # tier 2 patched
    assert "retrieved: 2026-07-30" in text


def test_apply_updates_is_noop_for_equal_values(tmp_path) -> None:
    path = tmp_path / "x.yaml"
    path.write_text(SAMPLE_YAML)
    assert not apply_updates(path, {"power:4.6": 0.25}, date(2026, 7, 30))
    assert path.read_text() == SAMPLE_YAML  # no formatting churn, no retrieved bump


def test_price_fingerprint_ignores_copy_but_not_prices() -> None:
    base = "<p>Tarifa X custa 0,1399 €/kWh e 0,4499 €/dia</p>"
    same_prices = "<div>Novo texto! 0,4499 por dia; energia 0,1399</div>"
    new_price = "<p>Tarifa X custa 0,1450 €/kWh e 0,4499 €/dia</p>"
    assert price_fingerprint(base) == price_fingerprint(same_prices)
    assert price_fingerprint(base) != price_fingerprint(new_price)
