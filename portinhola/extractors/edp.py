"""EDP Comercial bill extractor.

Layout notes (2022-2023 residential bills, dual-fuel and service-only):

- Page 1 is a summary; line tables live on later pages under section
  headers "Eletricidade", "Gás Natural", "Serviços" and "Taxas e Impostos".
- Table rows end with the VAT rate rendered as private-use glyphs the text
  layer dumps as ``(cid:NNNN)``: digit d is cid 1004+d and "%" is cid 1081,
  so ``(cid:1006)(cid:1007)(cid:1081)`` reads "23%".
- Consumption/potência rows carry only a date range ("25 out a 8 nov 2022")
  as description; the human description is the preceding block header
  ("Consumo real", "Potência (4,6 kVA)", ...).
- Amounts in the "Total s/IVA" column are VAT-exclusive, matching the
  semantics of the other extractors.
"""

import re
from datetime import date

from portinhola.core.billdata import BillData, Category, ParsedLine, ParsedSupply, Utility
from portinhola.extractors.base import Extractor, register

MONTHS = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}
MONTHS_FULL = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

# "25 out a 8 nov 2022" / "28 dez 2022 a 8 jan 2023"
RANGE_RE = re.compile(
    r"^(?P<d1>\d{1,2}) (?P<m1>[a-zç]{3})(?: (?P<y1>\d{4}))?"
    r" a (?P<d2>\d{1,2}) (?P<m2>[a-zç]{3}) (?P<y2>\d{4})$"
)
# desc/date-range, qty+unit, optional footnote marker digit, unit price,
# gross, optional percentage discount or plain abatement column,
# VAT-exclusive total, cid-encoded VAT
ROW_RE = re.compile(
    r"^(?P<head>.*?)\s?"
    r"(?P<qty>-?\d+(?:,\d+)?)\s*(?P<unit>kWh|dias|dia|meses|mês)?\s+(?:\d\s+)?"
    r"(?P<price>\d+,\d+)\s*€\s+"
    r"(?P<gross>-?\d+,\d+)\s*€"
    r"(?:\s+\d+%\s*\(-?\d+,\d+\s*€\)|\s+-?\d+,\d+\s*€(?=\s+-?\d+,\d+\s*€))?"
    r"\s+(?P<total>-?\d+,\d+)\s*€\s*"
    r"(?P<cid>(?:\(cid:\d+\))+)$"
)
CID_RE = re.compile(r"\(cid:(\d+)\)")
# Standalone reversal row in acerto documents: "Abatimentos -105,02 € (cid…)"
ABATE_RE = re.compile(r"^Abatimentos\s+(?P<total>-?\d+,\d+)\s*€\s*(?P<cid>(?:\(cid:\d+\))+)$")
CPE_RE = re.compile(r"\(Código Ponto Entrega\).*?(PT[\d ]{10,}[A-Z ]{2,4})", re.DOTALL)
CUI_RE = re.compile(r"\(Código Universal Instalação\).*?(PT[\d ]{10,}[A-Z ]{2,4})", re.DOTALL)
KVA_RE = re.compile(r"(?P<kva>\d+(?:,\d+)?)\s*kVA\s*\((?P<cycle>[^)]+)\)")
TIER_RE = re.compile(r"Escalão\s*(?P<tier>\d+)")
PERIOD_RE = re.compile(
    r"Período de faturação(?: eletricidade| Gás Natural)?[:\s]+"
    r"(?P<d1>\d{1,2}) de (?P<m1>[a-zç]+)(?: (?P<y1>\d{4}))?"
    r" a (?P<d2>\d{1,2}) de (?P<m2>[a-zç]+) (?P<y2>\d{4})"
)

TAX_NAMES = ("DGEG", "IEC", "IECGNC", "Contribuição Audiovisual", "Fixo", "Variável")


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _cid_vat(blob: str) -> int | None:
    digits = ""
    for value in CID_RE.findall(blob):
        n = int(value)
        if 1004 <= n <= 1013:
            digits += str(n - 1004)
    return int(digits) if digits else None


def _range_dates(head: str) -> tuple[date, date] | None:
    match = RANGE_RE.match(head)
    if not match:
        return None
    y2 = int(match["y2"])
    m1, m2 = MONTHS.get(match["m1"]), MONTHS.get(match["m2"])
    if m1 is None or m2 is None:
        return None
    y1 = int(match["y1"]) if match["y1"] else (y2 - 1 if m1 > m2 else y2)
    return date(y1, m1, int(match["d1"])), date(y2, m2, int(match["d2"]))


@register
class EdpExtractor(Extractor):
    name = "edp"
    version = "1"
    supplier_nifs = frozenset({"503504564"})

    def parse(self, pages: list[str]) -> BillData:
        lines: list[ParsedLine] = []
        utility: Utility | None = None
        in_taxes = False
        block = ""

        for page in pages[1:]:
            for raw in page.splitlines():
                stripped = raw.strip()
                if stripped == "Eletricidade":
                    utility, in_taxes = "electricity", False
                    continue
                if stripped == "Gás Natural":
                    utility, in_taxes = "gas", False
                    continue
                if stripped.startswith("Serviços"):
                    utility, in_taxes = None, False
                    continue
                if stripped.startswith("Taxas e Impostos"):
                    in_taxes = True
                    continue
                if abate := ABATE_RE.match(stripped):
                    lines.append(
                        ParsedLine(
                            description="Abatimentos",
                            category="energy",
                            utility=utility,
                            amount_cents=round(_num(abate["total"]) * 100),
                            vat_rate=_cid_vat(abate["cid"]),
                        )
                    )
                    continue
                match = ROW_RE.match(stripped)
                if not match:
                    # Remember block headers like "Potência (4,6 kVA)" or
                    # "Consumo real" for the date-range rows that follow.
                    if stripped and not stripped.startswith(("IVA", "Total", "Descrição")):
                        block = stripped
                    continue
                head = match["head"].strip()
                if head.startswith(("IVA", "Total")):
                    continue
                period = _range_dates(head) if head else None
                desc = block if (period or not head) else head
                if period is None and head:
                    desc = head
                line_utility = utility
                category = self._category(desc, match["unit"], utility, in_taxes)
                if "Mensalidade" in desc:
                    line_utility, category = None, "other"
                lines.append(
                    ParsedLine(
                        description=desc,
                        category=category,
                        utility=line_utility,
                        period_start=period[0] if period else None,
                        period_end=period[1] if period else None,
                        quantity=_num(match["qty"]),
                        unit=match["unit"],
                        unit_price=_num(match["price"]),
                        amount_cents=round(_num(match["total"]) * 100),
                        vat_rate=_cid_vat(match["cid"]),
                    )
                )

        first_page = pages[0] if pages else ""
        supplies = self._supplies(first_page)
        period_start, period_end = self._bill_period(first_page)
        return BillData(
            supplier_name="EDP Comercial",
            period_start=period_start,
            period_end=period_end,
            supplies=supplies,
            lines=lines,
        )

    @staticmethod
    def _category(
        desc: str, unit: str | None, utility: Utility | None, in_taxes: bool
    ) -> Category:
        if in_taxes or any(desc.startswith(name) for name in TAX_NAMES):
            return "tax"
        if unit == "kWh":
            return "energy"
        if unit in ("dia", "dias"):
            return "power" if utility == "electricity" else "fixed"
        return "other"

    @staticmethod
    def _supplies(first_page: str) -> list[ParsedSupply]:
        supplies: list[ParsedSupply] = []
        if cpe := CPE_RE.search(first_page):
            kva = KVA_RE.search(first_page)
            supplies.append(
                ParsedSupply(
                    utility="electricity",
                    identifier=cpe[1].replace(" ", ""),
                    power_kva=_num(kva["kva"]) if kva else None,
                    cycle=kva["cycle"].strip().lower() if kva else None,
                )
            )
        if cui := CUI_RE.search(first_page):
            tier = TIER_RE.search(first_page)
            supplies.append(
                ParsedSupply(
                    utility="gas",
                    identifier=cui[1].replace(" ", ""),
                    gas_tier=int(tier["tier"]) if tier else None,
                )
            )
        return supplies

    @staticmethod
    def _bill_period(first_page: str) -> tuple[date | None, date | None]:
        starts: list[date] = []
        ends: list[date] = []
        for match in PERIOD_RE.finditer(first_page):
            m1, m2 = MONTHS_FULL.get(match["m1"]), MONTHS_FULL.get(match["m2"])
            if m1 is None or m2 is None:
                continue
            y2 = int(match["y2"])
            y1 = int(match["y1"]) if match["y1"] else (y2 - 1 if m1 > m2 else y2)
            starts.append(date(y1, m1, int(match["d1"])))
            ends.append(date(y2, m2, int(match["d2"])))
        return (min(starts), max(ends)) if starts else (None, None)
