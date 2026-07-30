"""Endesa Tarifa Digital annex PDF → endesa-simples/bi/gas yamls.

We record the 20%-discounted values (permanent, conditional on online +
DD + digital invoice). The simples and bi tables have their own potência
ladders; the gas escalão 1-2 rows are zipped character-by-character in
the text layer, so they are rebuilt from word coordinates.
"""

import io
import re

import pdfplumber

from tools.tariff_watch.base import ParseFailed, pt_number

URL = "https://www.endesa.pt/content/dam/endesa-pt/precos/Tarifa-Digital-Luz-e-Gas.pdf"

KVAS = ("3,45", "4,6", "5,75", "6,9")

# "4,6  0,5730 0,4584 0,1444 0,174880 0,139904 0,0468 27,74"  (simples)
SIMPLES_RE = re.compile(
    r"^\s*(?P<kva>[\d,]+)\s+\d,\d{4}\s+(?P<power>\d,\d{4})\s+\d,\d{4}\s+"
    r"\d,\d{6}\s+(?P<energy>\d,\d{6})\s"
)
# "4,6  0,5095 0,4076 0,1444 0,217721 0,174177 0,0468 0,14889 0,119112 0,0468 26,89" (bi)
BI_RE = re.compile(
    r"^\s*(?P<kva>[\d,]+)\s+\d,\d{4}\s+(?P<power>\d,\d{4})\s+\d,\d{4}\s+"
    r"\d,\d{6}\s+(?P<fora>\d,\d{6})\s+\d,\d{4}\s+\d,\d{5}\s+(?P<vazio>\d,\d{6})\s"
)


def _norm_kva(raw: str) -> str | None:
    return {"3,45": "3.45", "4,6": "4.6", "5,75": "5.75", "6,9": "6.9"}.get(raw)


def _cluster_tokens(words: list) -> list[str]:
    """Join per-character words into numbers using x-gaps: characters
    inside a number are tightly kerned, column gaps are wide."""
    tokens: list[str] = []
    current = ""
    prev_end: float | None = None
    for word in sorted(words, key=lambda w: w["x0"]):
        if prev_end is not None and word["x0"] - prev_end > 2.5:
            tokens.append(current)
            current = ""
        current += word["text"]
        prev_end = word["x1"]
    if current:
        tokens.append(current)
    return tokens


def _gas_rows(page) -> dict[str, tuple[float, float]]:
    """Rebuild the escalão rows from word coordinates (rows 1-2 render as
    per-character words that plain text extraction zips together)."""
    rows: dict[int, list] = {}
    for word in page.extract_words():
        rows.setdefault(round(word["top"]), []).append(word)
    out: dict[str, tuple[float, float]] = {}
    tops = sorted(rows)
    for top in tops:
        line = [w["text"] for w in sorted(rows[top], key=lambda w: w["x0"])]
        if line not in (["1"], ["2"]):
            continue
        tier = line[0]
        for candidate in tops:
            if not (top < candidate <= top + 3):
                continue
            numbers = [
                t for t in _cluster_tokens(rows[candidate]) if re.fullmatch(r"\d+,\d+", t)
            ]
            if len(numbers) >= 5:
                # base fixo, discounted fixo, social, base energy, discounted energy…
                out[tier] = (pt_number(numbers[1]), pt_number(numbers[4]))
                break
    return out


def parse(pdf_bytes: bytes) -> dict:
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page2 = pdf.pages[1]
            layout = page2.extract_text(layout=True) or ""
            gas = _gas_rows(page2)
    except ParseFailed:
        raise
    except Exception as exc:
        raise ParseFailed(f"endesa: unreadable PDF: {exc}") from exc

    simples: dict[str, float] = {}
    simples_energy: float | None = None
    bi: dict[str, float] = {}
    bi_energy: tuple[float, float] | None = None
    # A bi-horária row is a superset of the simples shape, so try it first.
    for line in layout.splitlines():
        if match := BI_RE.match(line):
            kva = _norm_kva(match["kva"])
            if kva:
                bi[kva] = pt_number(match["power"])
                bi_energy = (pt_number(match["fora"]), pt_number(match["vazio"]))
        elif match := SIMPLES_RE.match(line):
            kva = _norm_kva(match["kva"])
            if kva:
                simples[kva] = pt_number(match["power"])
                simples_energy = pt_number(match["energy"])

    if set(simples) != {"3.45", "4.6", "5.75", "6.9"} or simples_energy is None:
        raise ParseFailed(f"endesa: simples table incomplete ({sorted(simples)})")
    if set(bi) != {"3.45", "4.6", "5.75", "6.9"} or bi_energy is None:
        raise ParseFailed(f"endesa: bi table incomplete ({sorted(bi)})")
    if set(gas) < {"1", "2"}:
        raise ParseFailed(f"endesa: gas escalões incomplete ({sorted(gas)})")

    return {
        "electricity/endesa-simples.yaml": {
            **{f"power:{k}": v for k, v in simples.items()},
            "simples_total": round(simples_energy, 4),
        },
        "electricity/endesa-bi.yaml": {
            **{f"power:{k}": v for k, v in bi.items()},
            "bi_fora_vazio": round(bi_energy[0], 4),
            "bi_vazio": round(bi_energy[1], 4),
        },
        "gas/endesa-gas.yaml": {
            "tier1_fixed": gas["1"][0],
            "tier1_energy": round(gas["1"][1], 4),
            "tier2_fixed": gas["2"][0],
            "tier2_energy": round(gas["2"][1], 4),
        },
    }
