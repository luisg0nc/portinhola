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
            seen.add(tariff.id)
            tariffs.append(tariff)
    return tariffs
