# Contributing a bill extractor

Portinhola parses supplier bills with one small Python module per supplier.
Adding support for your supplier is a self-contained PR. Machine-generated
PDFs parse deterministically — no ML, no heuristics.

## How extraction works

1. The uploaded PDF's text layer is extracted per page (`pdfplumber`), and
   the Portuguese fiscal QR (Portaria 195/2020) is decoded. The QR gives
   the authoritative fiscal fields: issuer NIF, document number, ATCUD,
   date, VAT bases and total.
2. The issuer NIF selects your extractor from the registry.
3. Your extractor turns the text pages into a `BillData`: billing period,
   supply points found on the bill (CPE/CUI/meter number), and categorized
   line items with amounts in **integer cents**.

## Writing one

Create `portinhola/extractors/<supplier>.py`:

```python
from portinhola.core.billdata import BillData, ParsedLine, ParsedSupply
from portinhola.extractors.base import Extractor, register


@register
class MySupplierExtractor(Extractor):
    name = "mysupplier"
    version = "1"
    supplier_nifs = frozenset({"500000000"})  # issuer NIF(s) on the bill/QR

    def parse(self, pages: list[str]) -> BillData:
        ...
```

Register the import in `portinhola/extractors/__init__.py`.

Line categories: `energy` (consumption), `power` (potência), `fixed`
(termos fixos/disponibilidade), `tax` (IEC, DGEG, CAV, TOS, taxas), and
`other`. Set `utility` per line — bills can be dual-fuel (G9 bills
electricity and gas on one invoice).

## Fixtures (required)

Tests never use real PDFs. Generate an anonymized text dump of your bill:

```bash
python tools/make_fixture.py my-bill.pdf tests/fixtures/mysupplier/pages_2026-01.txt
```

Extend `REPLACEMENTS` in `tools/make_fixture.py` if your personal data
survives, and **manually review the output** — no names, addresses, NIFs,
IBANs, or emails may be committed.

Then write `tests/test_extractor_mysupplier.py` following
`tests/test_extractor_g9.py`: it runs your extractor over every
`pages_*.txt` and compares against an `expected_*.json` snapshot
(`data.model_dump_json(indent=2)`). Sanity-check the snapshot against the
printed bill before committing: line count, section subtotals, supplies.

## Checklist

- [ ] Extractor module + registry import
- [ ] ≥1 anonymized fixture + expected JSON, manually privacy-reviewed
- [ ] `pytest`, `ruff check .`, `mypy portinhola` green
- [ ] README supplier table updated
