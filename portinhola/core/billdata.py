from datetime import date
from typing import Literal

from pydantic import BaseModel

Utility = Literal["electricity", "gas", "water"]
Category = Literal["energy", "power", "fixed", "tax", "other"]


class ParsedLine(BaseModel):
    description: str
    category: Category
    utility: Utility | None = None
    period_start: date | None = None
    period_end: date | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    amount_cents: int
    vat_rate: int | None = None


class ParsedSupply(BaseModel):
    utility: Utility
    identifier: str
    tariff_name: str = ""
    power_kva: float | None = None
    cycle: str | None = None
    gas_tier: int | None = None


class BillData(BaseModel):
    supplier_name: str
    period_start: date | None
    period_end: date | None
    supplies: list[ParsedSupply]
    lines: list[ParsedLine]
