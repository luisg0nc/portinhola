from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

TARIFFS_DIR = Path(__file__).parent.parent.parent / "tariffs"


class TariffLoadError(Exception):
    pass


class ElectricityPrices(BaseModel):
    model_config = ConfigDict(extra="forbid")

    power_eur_day: dict[str, float]
    energy_eur_kwh: dict[str, dict[str, float]]


class GasTier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixed_eur_day: float
    energy_eur_kwh: float
    fixed_reduced_share: float = 0.0


class GasPrices(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tiers: dict[str, GasTier]


class Promo(BaseModel):
    """Time-limited promotional phase (e.g. -15% energy, first 12 months)."""

    model_config = ConfigDict(extra="forbid")

    energy_pct: float = 0.0
    fixed_pct: float = 0.0  # off potência / termo fixo lines
    months: int
    conditions: str | None = None


class Tariff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    supplier: str
    supplier_nif: str | None = None
    name: str
    utility: str
    valid_from: date
    valid_to: date | None = None
    source_url: str
    retrieved: date
    # Human-readable eligibility note shown with the result — e.g. "requires
    # direct debit + e-invoice" or "base table; dual-bundle discounts apply".
    conditions: str | None = None
    promo: Promo | None = None
    electricity: ElectricityPrices | None = None
    gas: GasPrices | None = None


class VatConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reduced_rate: int
    standard_rate: int
    energy_reduced_kwh_per_30d: float
    power_reduced_max_kva: float


class TosGas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eur_kwh: float
    eur_day: float


class TaxConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iec_elec_eur_kwh: float
    dgeg_eur_month: float
    cav_eur_month: float
    iec_gas_eur_kwh: float
    tos_gas: dict[str, TosGas]
    default_municipality: str
    vat: VatConfig


def load_taxes(base_dir: Path | None = None) -> TaxConfig:
    base = base_dir or TARIFFS_DIR
    path = base / "taxes.yaml"
    try:
        data = yaml.safe_load(path.read_text())
        return TaxConfig.model_validate(data)
    except (OSError, ValidationError, yaml.YAMLError) as exc:
        raise TariffLoadError(f"{path}: {exc}") from exc


# Regulated network-access potência component (ERSE 2026): 0.0498 €/day
# per kVA, linear — every supplier must pass it through before margin. A
# ladder below this floor is fabricated data, not a cheap tariff.
ACCESS_FLOOR_EUR_DAY_PER_KVA = 0.0498


def _check_power_floor(tariff: "Tariff", filename: str) -> None:
    if tariff.electricity is None:
        return
    for kva_str, price in tariff.electricity.power_eur_day.items():
        floor = ACCESS_FLOOR_EUR_DAY_PER_KVA * float(kva_str)
        if price < floor * 0.999:
            raise TariffLoadError(
                f"{filename}: potência {price} €/day at {kva_str} kVA is below "
                f"the regulated access floor ({floor:.4f}) — implausible data"
            )


def load_tariffs(base_dir: Path | None = None) -> list[Tariff]:
    base = base_dir or TARIFFS_DIR
    if not base.exists():
        raise TariffLoadError(f"tariffs directory not found: {base}")
    tariffs: list[Tariff] = []
    seen: set[str] = set()
    for sub in ("electricity", "gas"):
        directory = base / sub
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text())
                tariff = Tariff.model_validate({**data, "id": path.stem})
            except (ValidationError, yaml.YAMLError) as exc:
                raise TariffLoadError(f"{path.name}: {exc}") from exc
            if tariff.id in seen:
                raise TariffLoadError(f"duplicate tariff id: {tariff.id}")
            _check_power_floor(tariff, path.name)
            seen.add(tariff.id)
            tariffs.append(tariff)
    return tariffs


class DualDiscounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    electricity_energy_pct: float = 0.0
    gas_energy_pct: float = 0.0
    fixed_eur_month: float = 0.0
    # When set, the discounts above are a promotional phase limited to the
    # first N months; steady-state totals exclude them.
    promo_months: int | None = None


class DualBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    supplier: str
    name: str
    electricity_tariff: str
    gas_tariff: str
    valid_from: date
    valid_to: date | None = None
    source_url: str
    retrieved: date
    conditions: str | None = None
    discounts: DualDiscounts = DualDiscounts()


def load_dual_bundles(
    tariffs: list[Tariff], base_dir: Path | None = None
) -> list[DualBundle]:
    """Load tariffs/dual/*.yaml, validating references against `tariffs`."""
    base = base_dir or TARIFFS_DIR
    directory = base / "dual"
    if not directory.exists():
        return []
    by_id = {t.id: t for t in tariffs}
    bundles: list[DualBundle] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text())
            bundle = DualBundle.model_validate({**data, "id": path.stem})
        except (ValidationError, yaml.YAMLError) as exc:
            raise TariffLoadError(f"{path.name}: {exc}") from exc
        for ref, utility in (
            (bundle.electricity_tariff, "electricity"),
            (bundle.gas_tariff, "gas"),
        ):
            tariff = by_id.get(ref)
            if tariff is None or tariff.utility != utility:
                raise TariffLoadError(
                    f"{path.name}: {ref!r} is not a known {utility} tariff"
                )
        bundles.append(bundle)
    return bundles
