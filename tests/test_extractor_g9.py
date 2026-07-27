import json
from pathlib import Path

import pytest

from portinhola.extractors.g9 import G9Extractor
from tests.fixtures.loader import load_pages

FIXDIR = Path(__file__).parent / "fixtures" / "g9"
CASES = sorted(p.stem.removeprefix("pages_") for p in FIXDIR.glob("pages_*.txt"))


@pytest.mark.parametrize("case", CASES)
def test_g9_extractor_matches_expected(case: str) -> None:
    pages = load_pages(f"g9/pages_{case}.txt")
    data = G9Extractor().parse(pages)
    expected = json.loads((FIXDIR / f"expected_{case}.json").read_text())
    assert json.loads(data.model_dump_json()) == expected


def test_g9_supplies_detected() -> None:
    pages = load_pages(f"g9/pages_{CASES[-1]}.txt")
    data = G9Extractor().parse(pages)
    utilities = {s.utility for s in data.supplies}
    assert utilities == {"electricity", "gas"}
    elec = next(s for s in data.supplies if s.utility == "electricity")
    assert elec.identifier.startswith("PT")
    assert elec.power_kva == 4.6
    assert elec.cycle == "simples"


def test_g9_line_categories() -> None:
    pages = load_pages(f"g9/pages_{CASES[-1]}.txt")
    data = G9Extractor().parse(pages)
    categories = {line.category for line in data.lines}
    assert {"energy", "power", "tax", "fixed"} <= categories
    assert all(line.utility in ("electricity", "gas") for line in data.lines)
    gas_lines = [line for line in data.lines if line.utility == "gas"]
    assert gas_lines, "dual-fuel bill must have gas lines"
