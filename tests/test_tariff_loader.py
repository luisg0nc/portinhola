from pathlib import Path

import pytest

from portinhola.core.tariffs import TariffLoadError, load_tariffs, load_taxes


def test_bundled_tariffs_load() -> None:
    tariffs = load_tariffs()
    ids = {t.id for t in tariffs}
    assert "g9-simples" in ids
    assert "g9-gas" in ids
    g9 = next(t for t in tariffs if t.id == "g9-simples")
    assert g9.utility == "electricity"
    assert g9.electricity is not None
    assert g9.electricity.energy_eur_kwh["simples"]["total"] == 0.1547
    assert g9.electricity.power_eur_day["4.6"] == 0.3493
    gas = next(t for t in tariffs if t.id == "g9-gas")
    assert gas.gas is not None
    assert gas.gas.tiers["2"].energy_eur_kwh == pytest.approx(0.10722)


def test_taxes_load() -> None:
    taxes = load_taxes()
    assert taxes.iec_elec_eur_kwh == 0.001
    assert taxes.vat.reduced_rate == 6
    assert taxes.vat.standard_rate == 23
    assert taxes.vat.energy_reduced_kwh_per_30d == 200
    assert "valongo" in taxes.tos_gas


def test_invalid_file_raises(tmp_path) -> None:
    (tmp_path / "electricity").mkdir(parents=True)
    (tmp_path / "electricity" / "bad.yaml").write_text("supplier: X\nbogus_field: 1\n")
    (tmp_path / "taxes.yaml").write_text("")
    with pytest.raises(TariffLoadError) as exc:
        load_tariffs(tmp_path)
    assert "bad.yaml" in str(exc.value)


def test_duplicate_id_raises(tmp_path) -> None:
    (tmp_path / "electricity").mkdir(parents=True)
    (tmp_path / "gas").mkdir(parents=True)
    minimal = (
        "supplier: A\nname: A Plan\nutility: electricity\n"
        "valid_from: 2026-01-01\nsource_url: http://x\nretrieved: 2026-07-28\n"
        "electricity:\n  power_eur_day: {'4.6': 0.3}\n"
        "  energy_eur_kwh: {simples: {total: 0.15}}\n"
    )
    (tmp_path / "electricity" / "dup.yaml").write_text(minimal)
    (tmp_path / "gas" / "dup.yaml").write_text(
        minimal.replace("electricity", "gas").replace(
            "gas:\n  power_eur_day: {'4.6': 0.3}\n  energy_eur_kwh: {simples: {total: 0.15}}",
            "gas:\n  tiers: {'1': {fixed_eur_day: 0.1, energy_eur_kwh: 0.1}}",
        )
    )
    with pytest.raises(TariffLoadError):
        load_tariffs(tmp_path)


def test_missing_dir_is_error() -> None:
    with pytest.raises(TariffLoadError):
        load_tariffs(Path("/nonexistent-tariffs"))
