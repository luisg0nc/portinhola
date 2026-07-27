import re
from datetime import date

from portinhola.core.billdata import BillData, Category, ParsedLine, ParsedSupply, Utility
from portinhola.extractors.base import Extractor, register

LINE_RE = re.compile(
    r"^(?P<desc>.+?)\s+"
    r"(?P<ps>\d{4}-\d{2}-\d{2})\s+(?P<pe>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<qty>-?[\d.,]+)\s*(?P<unit>kWh|dias|mês|meses|m3)\s+"
    r"(?P<vat>\d+)%\s+(?P<price>[\d.,]+)\s+"
    r"(?:(?P<gross>-?[\d.,]+)\s+)?(?P<total>-?[\d.,]+)$"
)
# The PDF text layer inserts a stray space after the first letter of many
# lines ("E letricidade", "Im posto"); collapse it before matching.
STRAY_SPACE_RE = re.compile(r"^([A-Za-zÀ-ÿ]{1,2}) (?=[a-zà-ÿ])")
CPE_RE = re.compile(r"CPE:\s*(?P<cpe>PT\w+)")
CUI_RE = re.compile(r"CUI:\s*(?P<cui>PT\w+)")
KVA_RE = re.compile(r"Serviço:\s*(?P<kva>[\d,]+)\s*kVA\s*\((?P<cycle>[^)]+)\)")
TIER_RE = re.compile(r"Serviço:.*Escalão-(?P<tier>\d+)")

TAX_MARKERS = (
    "Imposto especial",
    "Contribuição audiovisual",
    "Taxa de exploração",
    "Taxa de ocupação de subsolo",
    "tarifa social",
)
GAS_MARKERS = ("Gás", "gás", "SNG", "subsolo")


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)


def _date(s: str) -> date:
    year, month, day = s.split("-")
    return date(int(year), int(month), int(day))


def _category(desc: str) -> Category:
    if "potência" in desc:
        return "power"
    if any(marker in desc for marker in TAX_MARKERS):
        return "tax"
    if "termo fixo" in desc:
        return "fixed"
    if "energia" in desc:
        return "energy"
    return "other"


def _utility(desc: str) -> Utility:
    return "gas" if any(marker in desc for marker in GAS_MARKERS) else "electricity"


@register
class G9Extractor(Extractor):
    name = "g9"
    version = "1"
    supplier_nifs = frozenset({"504435302"})

    def parse(self, pages: list[str]) -> BillData:
        lines: list[ParsedLine] = []
        for page in pages[1:]:
            for raw in page.splitlines():
                cleaned = STRAY_SPACE_RE.sub(r"\1", raw.strip())
                match = LINE_RE.match(cleaned)
                if not match:
                    continue
                desc = match["desc"].strip()
                lines.append(
                    ParsedLine(
                        description=desc,
                        category=_category(desc),
                        utility=_utility(desc),
                        period_start=_date(match["ps"]),
                        period_end=_date(match["pe"]),
                        quantity=_num(match["qty"]),
                        unit=match["unit"],
                        unit_price=_num(match["price"]),
                        amount_cents=round(_num(match["total"]) * 100),
                        vat_rate=int(match["vat"]),
                    )
                )

        first_page = pages[0] if pages else ""
        supplies: list[ParsedSupply] = []
        if cpe := CPE_RE.search(first_page):
            kva = KVA_RE.search(first_page)
            supplies.append(
                ParsedSupply(
                    utility="electricity",
                    identifier=cpe["cpe"],
                    power_kva=_num(kva["kva"]) if kva else None,
                    cycle=kva["cycle"].strip().lower() if kva else None,
                )
            )
        if cui := CUI_RE.search(first_page):
            tier = TIER_RE.search(first_page)
            supplies.append(
                ParsedSupply(
                    utility="gas",
                    identifier=cui["cui"],
                    gas_tier=int(tier["tier"]) if tier else None,
                )
            )

        elec_periods = [
            (line.period_start, line.period_end)
            for line in lines
            if line.utility == "electricity" and line.period_start and line.period_end
        ]
        period_start = min((start for start, _ in elec_periods), default=None)
        period_end = max((end for _, end in elec_periods), default=None)
        return BillData(
            supplier_name="G9",
            period_start=period_start,
            period_end=period_end,
            supplies=supplies,
            lines=lines,
        )
