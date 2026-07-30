import json
from pathlib import Path

import pytest

from portinhola.extractors.edp import EdpExtractor
from tests.fixtures.loader import load_pages

FIXDIR = Path(__file__).parent / "fixtures" / "edp"
CASES = sorted(p.stem.removeprefix("pages_") for p in FIXDIR.glob("pages_*.txt"))


@pytest.mark.parametrize("case", CASES)
def test_edp_extractor_matches_expected(case: str) -> None:
    pages = load_pages(f"edp/pages_{case}.txt")
    data = EdpExtractor().parse(pages)
    expected = json.loads((FIXDIR / f"expected_{case}.json").read_text())
    assert json.loads(data.model_dump_json()) == expected


def test_edp_dual_fuel_supplies_and_period() -> None:
    pages = load_pages("edp/pages_2022-12.txt")
    data = EdpExtractor().parse(pages)
    assert {s.utility for s in data.supplies} == {"electricity", "gas"}
    elec = next(s for s in data.supplies if s.utility == "electricity")
    assert elec.identifier == "PT0002000000000000XX"
    assert elec.power_kva == 4.6
    gas = next(s for s in data.supplies if s.utility == "gas")
    assert gas.gas_tier == 1
    assert str(data.period_start) == "2022-10-25"
    assert str(data.period_end) == "2022-12-08"


def test_edp_grand_total_matches_document_sum() -> None:
    """The PDF bundles several sub-invoices (electricity, CAV, gas,
    services); line totals plus per-line VAT must reproduce the document's
    grand total of 135,43 €."""
    pages = load_pages("edp/pages_2022-12.txt")
    data = EdpExtractor().parse(pages)
    net = sum(line.amount_cents for line in data.lines)
    vat = sum(round(line.amount_cents * (line.vat_rate or 0) / 100) for line in data.lines)
    assert abs(net + vat - 13543) <= 2  # ±2 cents of per-line rounding


def test_edp_vat_decoded_from_cid_glyphs() -> None:
    pages = load_pages("edp/pages_2022-12.txt")
    data = EdpExtractor().parse(pages)
    assert {line.vat_rate for line in data.lines} == {6, 23}


def test_edp_credit_note_lines_are_negative() -> None:
    pages = load_pages("edp/pages_nc_2023-05.txt")
    data = EdpExtractor().parse(pages)
    assert len(data.lines) == 1
    assert data.lines[0].amount_cents == -642
