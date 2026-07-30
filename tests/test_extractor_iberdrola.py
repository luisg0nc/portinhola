import json
from pathlib import Path

import pytest

from portinhola.extractors.iberdrola import IberdrolaExtractor
from tests.fixtures.loader import load_pages

FIXDIR = Path(__file__).parent / "fixtures" / "iberdrola"
CASES = sorted(p.stem.removeprefix("pages_") for p in FIXDIR.glob("pages_*.txt"))


@pytest.mark.parametrize("case", CASES)
def test_iberdrola_extractor_matches_expected(case: str) -> None:
    pages = load_pages(f"iberdrola/pages_{case}.txt")
    data = IberdrolaExtractor().parse(pages)
    expected = json.loads((FIXDIR / f"expected_{case}.json").read_text())
    assert json.loads(data.model_dump_json()) == expected


def test_iberdrola_tabular_electricity_net() -> None:
    """2023 layout: energy+potência+discounts+taxes must sum to the bill's
    own VAT-base total (26,67 €)."""
    pages = load_pages("iberdrola/pages_2023-02.txt")
    data = IberdrolaExtractor().parse(pages)
    assert sum(line.amount_cents for line in data.lines) == 2667
    assert {line.category for line in data.lines} >= {"energy", "power", "tax"}


def test_iberdrola_plano_vantagem_layout() -> None:
    """2024 layout: per-line VAT is printed; discounts are negative."""
    pages = load_pages("iberdrola/pages_2024-03.txt")
    data = IberdrolaExtractor().parse(pages)
    assert sum(line.amount_cents for line in data.lines) == 6530
    discounts = [line for line in data.lines if "Desconto" in line.description]
    assert discounts and all(line.amount_cents < 0 for line in discounts)
    cav = next(line for line in data.lines if "Audiovisual" in line.description)
    assert cav.vat_rate == 6
    assert str(data.period_start) == "2024-02-08"


def test_iberdrola_gas_layout() -> None:
    pages = load_pages("iberdrola/pages_gas_2024-11.txt")
    data = IberdrolaExtractor().parse(pages)
    assert sum(line.amount_cents for line in data.lines) == 4719
    gas = next(s for s in data.supplies if s.utility == "gas")
    assert gas.identifier == "PT1601000000000000XX"
    assert gas.gas_tier == 2
    assert all(line.utility in ("gas", None) for line in data.lines)


def test_iberdrola_credit_note_yields_no_lines() -> None:
    """Credit notes re-list the corrected bill; parsing them would double
    charges, so the extractor must return no lines (bill stays QR-only)."""
    pages = ["NOTA DE CRÉDITO Página 1 / 3", "Energia Real Consumida 10 kWh x 0,1 €/kWh 1,00 €"]
    data = IberdrolaExtractor().parse(pages)
    assert data.lines == []
