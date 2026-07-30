import re
from datetime import date

from portinhola.core.billdata import BillData, Category, ParsedLine, ParsedSupply
from portinhola.extractors.base import Extractor, register

# FAC layout (2025+): rows end with amount (4 decimals) + VAT code,
# optionally preceded by a unit price (6 decimals). The quantity
# ("Faturado") column always precedes.
LINE_RE = re.compile(
    r"^(?P<desc>.+?)\s+"
    r"(?P<qty>-?\d+,\d{4})\s+"
    r"(?:(?P<price>-?\d+,\d{6})\s+)?"
    r"(?P<amount>-?\d+,\d{4})\s+"
    r"\((?P<code>\d+)\)"
)
# Older "Documento de Pagamento" layout (~2024): each row carries its own
# period dates, a quantity with unit text, a 6-decimal price and a
# 2-decimal amount, e.g.
# "1 Esc. Consumo Água 0 - 5 m3 em 30 dias 2023-12-22 2023-12-31
#  2,0000 m3 em 10 dias 0,893300 1,79 (2)"
OLD_LINE_RE = re.compile(
    r"^(?P<desc>.+?)\s+"
    r"(?P<ps>\d{4}-\d{2}-\d{2})\s+(?P<pe>\d{4}-\d{2}-\d{2})\s+"
    r"(?:Períodos Anteriores\s+|(?P<qty>-?\d+(?:,\d+)?)\s*(?:m3 em \d+ dias|m3|mm|dias)?\s+)"
    r"(?P<price>-?\d+,\d{6})\s+"
    r"(?P<amount>-?\d+,\d{1,2})\s+"
    r"\((?P<code>\d+)\)"
)
PERIOD_RE = re.compile(r"(\d{4}-\d{2}-\d{2}) ~ (\d{4}-\d{2}-\d{2})")
LOCAL_RE = re.compile(r"Local Consumo:\s*(?P<id>\d+)")

# FAC layout: (2) água 6%, (3) saneamento 6%, (23) não sujeito (TRSU).
# Old layout: (2) água 6%, (4) saneamento 6%, (5) não sujeito (TRSU).
VAT_CODES: dict[str, int | None] = {"2": 6, "3": 6, "4": 6, "5": None, "23": None}

CATEGORY_PREFIXES: list[tuple[str, Category]] = [
    ("Consumo Água", "energy"),
    ("Saneamento Variável", "energy"),
    ("Tarifa de Disponibilidade", "fixed"),
    ("Tar.Disp.", "fixed"),
    ("Resíduos Sólidos Fixo", "fixed"),
    ("Taxa Recursos Hídricos", "tax"),
    ("Taxa Gestão Resíduos", "tax"),
    ("Resíduos Sólidos Variável", "other"),
]


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _date(s: str) -> date:
    year, month, day = s.split("-")
    return date(int(year), int(month), int(day))


def _category(desc: str) -> Category:
    # Old-layout descriptions carry an "N Esc. " tier prefix, so match by
    # containment rather than prefix.
    for marker, category in CATEGORY_PREFIXES:
        if marker in desc:
            return category
    return "other"


@register
class BeWaterExtractor(Extractor):
    name = "bewater"
    version = "1"
    supplier_nifs = frozenset({"505084040"})

    def parse(self, pages: list[str]) -> BillData:
        text = "\n".join(pages)

        period_start = period_end = None
        if period := PERIOD_RE.search(text):
            period_start = _date(period.group(1))
            period_end = _date(period.group(2))

        supplies: list[ParsedSupply] = []
        if local := LOCAL_RE.search(text):
            supplies.append(ParsedSupply(utility="water", identifier=local["id"]))

        lines: list[ParsedLine] = []
        for page in pages[1:]:
            for raw in page.splitlines():
                stripped = raw.strip()
                if match := LINE_RE.match(stripped):
                    line_start, line_end = period_start, period_end
                elif match := OLD_LINE_RE.match(stripped):
                    line_start, line_end = _date(match["ps"]), _date(match["pe"])
                else:
                    continue
                desc = match["desc"].strip()
                if desc.startswith(("(", "IVA")):
                    continue
                qty = match.groupdict().get("qty")
                lines.append(
                    ParsedLine(
                        description=desc,
                        category=_category(desc),
                        utility="water",
                        period_start=line_start,
                        period_end=line_end,
                        quantity=_num(qty) if qty else None,
                        unit=None,
                        unit_price=_num(match["price"]) if match["price"] else None,
                        amount_cents=round(_num(match["amount"]) * 100),
                        vat_rate=VAT_CODES.get(match["code"]),
                    )
                )

        return BillData(
            supplier_name="Águas de Valongo (Be Water)",
            period_start=period_start,
            period_end=period_end,
            supplies=supplies,
            lines=lines,
        )
