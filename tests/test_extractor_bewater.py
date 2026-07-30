import json
from pathlib import Path

import pytest

from portinhola.extractors.bewater import BeWaterExtractor
from tests.fixtures.loader import load_pages

FIXDIR = Path(__file__).parent / "fixtures" / "bewater"
CASES = sorted(p.stem.removeprefix("pages_") for p in FIXDIR.glob("pages_*.txt"))


@pytest.mark.parametrize("case", CASES)
def test_bewater_extractor_matches_expected(case: str) -> None:
    pages = load_pages(f"bewater/pages_{case}.txt")
    data = BeWaterExtractor().parse(pages)
    expected = json.loads((FIXDIR / f"expected_{case}.json").read_text())
    assert json.loads(data.model_dump_json()) == expected


def test_bewater_supply_and_period() -> None:
    pages = load_pages(f"bewater/pages_{CASES[-1]}.txt")
    data = BeWaterExtractor().parse(pages)
    assert [s.utility for s in data.supplies] == ["water"]
    assert data.period_start is not None and data.period_end is not None
    assert sum(1 for line in data.lines if line.category == "energy") >= 2


def test_bewater_vat_code_mapping() -> None:
    pages = load_pages(f"bewater/pages_{CASES[-1]}.txt")
    data = BeWaterExtractor().parse(pages)
    rates = {line.vat_rate for line in data.lines}
    assert rates <= {6, None}
    assert all(line.utility == "water" for line in data.lines)


def test_bewater_old_layout_reconciles_to_document_total() -> None:
    """Pre-2025 'Documento de Pagamento' layout: per-row periods, acerto
    reversal rows without quantity, 1-2 decimal amounts."""
    pages = load_pages("bewater/pages_old_2024-01.txt")
    data = BeWaterExtractor().parse(pages)
    assert len(data.lines) == 19
    net = sum(line.amount_cents for line in data.lines)
    vat = sum(round(line.amount_cents * (line.vat_rate or 0) / 100) for line in data.lines)
    assert net == 3518  # "Total sem IVA 35,18€"
    assert net + vat == 3672  # "TOTAL 36,72€"
    assert data.supplies[0].identifier == "200000"
    assert all(line.utility == "water" for line in data.lines)
    # per-row periods, not the bill period
    assert any(str(line.period_end) == "2023-12-31" for line in data.lines)
