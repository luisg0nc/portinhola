"""Iberdrola bill extractor.

Two residential layouts appear in the wild:

- The tabular layout (electricity ~2023, gas ~2024): rows read
  ``<desc> <qty> <unit> x <price> [€]/<unit> <amount> €`` with negative
  amounts in parentheses, and separate ``Desconto ... % ... (x) €`` rows.
  Per-line VAT is mostly absent (the bill aggregates VAT bases), so
  ``vat_rate`` is only set where the description carries "(IVA n%)".
- The "Plano Vantagem" layout (electricity ~2024): rows read
  ``<desc> <qty> <unit> <price> €/<unit> <amount> € <vat>%`` and
  ``Desconto: <desc> n% (x) € <vat>%``.

The PDF text layer merges the page's side column into some rows, so every
pattern anchors on the left-hand structure and takes the first amount.
Electricity bills print the CPE masked ("Ocultados por segurança"), so
supplies may be empty; the gas CUI is printed in full.
"""

import re
from datetime import date

from portinhola.core.billdata import BillData, Category, ParsedLine, ParsedSupply, Utility
from portinhola.extractors.base import Extractor, register

AMT = r"(?:\((?P<amt_neg>\d+(?:[.,]\d+)*)\)|(?P<amt>-?\d+(?:[.,]\d+)*))\s*€"

# "Energia Real Consumida 153 kWh x 0,1274 /kWh 19,49 €"
# "Termo Tarifario Fixo 31 dias x 0,2065 €/dia 6,40 €"
# "Manutenção Gas Iberdrola (23/10/2024-19/11/2024) 0,89 meses x 6,95 €/mês 6,19 €"
TABULAR_RE = re.compile(
    r"^(?P<desc>.+?)\s+(?P<qty>-?\d+(?:[.,]\d+)*)\s*(?P<unit>kWh|dias|mês|meses)\s*"
    r"x\s*(?P<price>-?\d+(?:[.,]\d+)*)\s*€?\s*/\s*(?:kWh|dia|mês)\s+" + AMT
)
# "Desconto Termo Fixo 2,13 % s/6,4 € (0,14) €" / "Desconto sobre o consumo 1% (0,21) €"
TABULAR_DISC_RE = re.compile(
    r"^(?P<desc>Desconto[^%(]*?)\s*(?P<pct>\d+(?:[.,]\d+)?)\s*%"
    r"(?:\s+s/\s*\d+(?:[.,]\d+)*\s*€)?\s+\((?P<amt_neg>\d+(?:[.,]\d+)*)\)\s*€"
)
# "Desconto na Proteção Elétrica Lar (3,99) €" — no percentage printed
TABULAR_DISC_FLAT_RE = re.compile(
    r"^(?P<desc>Desconto[^%(€]*?)\s+\((?P<amt_neg>\d+(?:[.,]\d+)*)\)\s*€"
)
# "Taxa Exploração DGEG 0,07 €" / "Taxa Ocupação Subsolo (19/08/2024-18/10/2024) (1) 2,68 €"
BARE_TAX_RE = re.compile(
    r"^(?P<desc>(?:Taxa|Imposto|IE Consumo|IEC|Contribuição)[^€]*?)\s+" + AMT
)
# Plano Vantagem: "Energia Real: Simples 283 kWh 0,176 €/kWh 49,81 € 23%"
PLANO_RE = re.compile(
    r"^(?P<desc>.+?)\s+(?P<qty>-?\d+(?:[.,]\d+)*)\s*(?P<unit>kWh|dias|mês|meses|Und\.)\s+"
    r"(?P<price>-?\d+(?:[.,]\d+)*)\s*€/(?:kWh|dia|mês|Und\.)\s+"
    r"(?P<amt>-?\d+(?:[.,]\d+)*)\s*€\s+(?P<vat>\d+)%"
)
# "Desconto: Energia Real 2% (1,06) € 23%"
PLANO_DISC_RE = re.compile(
    r"^(?P<desc>Desconto: .+?)\s+\d+(?:[.,]\d+)?%\s+\((?P<amt_neg>\d+(?:[.,]\d+)*)\)\s*€"
    r"\s+(?P<vat>\d+)%"
)
INLINE_VAT_RE = re.compile(r"\(IVA (?P<vat>\d+)%\)")
CUI_RE = re.compile(r"\(CUI\):?\s*(PT[\d ]{10,}[A-Z ]{2,4})")
CPE_RE = re.compile(r"CPE[^:]*:?\s*(PT\d{12}[A-Z]{2})")
KVA_RE = re.compile(r"Potência [Cc]ontratada:?\s*(?P<kva>\d+(?:,\d+)?)\s*kVA")
TIER_RE = re.compile(r"Escalão\s*(?P<tier>\d+)")
PERIOD_RE = re.compile(
    r"Período d[ae] [Ff]atura(?:ção)?:?\s*"
    r"(?P<d1>\d{2})[/-](?P<m1>\d{2})[/-](?P<y1>\d{4})\s*-\s*"
    r"(?P<d2>\d{2})[/-](?P<m2>\d{2})[/-](?P<y2>\d{4})"
)
# Plano Vantagem prints the label and the dates on different lines; fall
# back to the first spaced date range anywhere on the page.
PERIOD_FALLBACK_RE = re.compile(
    r"(?P<d1>\d{2})[/-](?P<m1>\d{2})[/-](?P<y1>\d{4}) - "
    r"(?P<d2>\d{2})[/-](?P<m2>\d{2})[/-](?P<y2>\d{4})"
)

SKIP_PREFIXES = ("IVA ", "TOTAL", "VALOR TOTAL", "SALDO", "NESTA FATURA")
TAX_MARKERS = ("Taxa", "Imposto", "IEC", "IE Consumo", "Contribuição", "Subsolo")
SERVICE_MARKERS = ("Proteção", "Manutenção", "Assistência")


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _amount_cents(match: re.Match) -> int:
    groups = match.groupdict()
    if groups.get("amt_neg"):
        return -round(_num(groups["amt_neg"]) * 100)
    return round(_num(groups["amt"]) * 100)


@register
class IberdrolaExtractor(Extractor):
    name = "iberdrola"
    version = "1"
    supplier_nifs = frozenset({"502124083"})

    def parse(self, pages: list[str]) -> BillData:
        text = "\f".join(pages)
        utility: Utility = "gas" if CUI_RE.search(text) else "electricity"

        if "NOTA DE CRÉDITO" in text:
            # Credit notes re-list the corrected bill's rows in full; parsing
            # them would double the original charges. Degrade to QR-only.
            return BillData(
                supplier_name="Iberdrola",
                period_start=None,
                period_end=None,
                supplies=[],
                lines=[],
            )

        lines: list[ParsedLine] = []
        for page in pages:
            for raw in page.splitlines():
                # Some Iberdrola PDFs emit the euro sign as U+0080
                # (cp1252 leftover) in the "€/kWh" price units.
                stripped = raw.replace("", "€").strip()
                if not stripped or stripped.startswith(SKIP_PREFIXES):
                    continue
                parsed = self._parse_row(stripped, utility)
                if parsed is not None:
                    lines.append(parsed)

        supplies = self._supplies(text, utility)
        period = PERIOD_RE.search(text) or PERIOD_FALLBACK_RE.search(text)
        period_start = period_end = None
        if period:
            period_start = date(int(period["y1"]), int(period["m1"]), int(period["d1"]))
            period_end = date(int(period["y2"]), int(period["m2"]), int(period["d2"]))
        return BillData(
            supplier_name="Iberdrola",
            period_start=period_start,
            period_end=period_end,
            supplies=supplies,
            lines=lines,
        )

    def _parse_row(self, line: str, utility: Utility) -> ParsedLine | None:
        for pattern in (
            PLANO_RE,
            PLANO_DISC_RE,
            TABULAR_RE,
            TABULAR_DISC_RE,
            TABULAR_DISC_FLAT_RE,
            BARE_TAX_RE,
        ):
            match = pattern.match(line)
            if not match:
                continue
            groups = match.groupdict()
            desc = groups["desc"].strip()
            vat = int(groups["vat"]) if groups.get("vat") else None
            if vat is None:
                if inline := INLINE_VAT_RE.search(desc):
                    vat = int(inline["vat"])
                elif "Audiovisual" in desc:
                    vat = 6
            return ParsedLine(
                description=desc,
                category=self._category(desc),
                utility=None if self._is_service(desc) else utility,
                quantity=_num(groups["qty"]) if groups.get("qty") else None,
                unit=groups.get("unit"),
                unit_price=_num(groups["price"]) if groups.get("price") else None,
                amount_cents=_amount_cents(match),
                vat_rate=vat,
            )
        return None

    @staticmethod
    def _is_service(desc: str) -> bool:
        return any(marker in desc for marker in SERVICE_MARKERS)

    @staticmethod
    def _category(desc: str) -> Category:
        lowered = desc.lower()
        if any(marker in desc for marker in TAX_MARKERS) and "Desconto" not in desc:
            return "tax"
        if IberdrolaExtractor._is_service(desc):
            return "other"
        if "potência" in lowered:
            return "power"
        if "termo" in lowered and "fixo" in lowered:
            return "fixed"
        if "energia" in lowered or "consumo" in lowered or "ajuste" in lowered:
            return "energy"
        return "other"

    @staticmethod
    def _supplies(text: str, utility: Utility) -> list[ParsedSupply]:
        supplies: list[ParsedSupply] = []
        if utility == "electricity":
            if cpe := CPE_RE.search(text):
                kva = KVA_RE.search(text)
                supplies.append(
                    ParsedSupply(
                        utility="electricity",
                        identifier=cpe[1],
                        power_kva=_num(kva["kva"]) if kva else None,
                    )
                )
        elif cui := CUI_RE.search(text):
            tier = TIER_RE.search(text)
            supplies.append(
                ParsedSupply(
                    utility="gas",
                    identifier=cui[1].replace(" ", ""),
                    gas_tier=int(tier["tier"]) if tier else None,
                )
            )
        return supplies
