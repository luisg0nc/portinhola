"""Galp residencial price-table PDF → galp-simples.yaml, galp-gas.yaml.

Final prices incl. network access, excl. VAT. The simples/bi energy for
3.45-5.75 kVA is one row band; the potência ladder is explicit.
"""

import io
import re

import pdfplumber

from tools.tariff_watch.base import ParseFailed, pt_number

URL = (
    "https://www.galp.com/pt/casa/system/files/2025-12/"
    "Tabela%20Pre%C3%A7os%20e%20Descontos_Residencial.pdf"
)

LADDER_RE = re.compile(
    r"^(?P<kva>3,45|4,60|5,75|6,90)\s+(?P<power>\d,\d{4})\s+(?P<simples>\d,\d{4})"
    r"\s+(?P<fora>\d,\d{4})\s+(?P<vazio>\d,\d{4})",
    re.MULTILINE,
)
GAS_RE = re.compile(
    r"(?P<tier>[12])º escalão[^\n]*?\s(?P<fixed>\d,\d{4})\s+(?P<energy>\d,\d{4})"
)


def parse(pdf_bytes: bytes) -> dict:
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        raise ParseFailed(f"galp: unreadable PDF: {exc}") from exc

    ladder: dict[str, float] = {}
    simples: dict[str, float] = {}
    bi: dict[str, tuple[float, float]] = {}
    # first table only (TABELA DE PREÇOS, before TARIFA DE COMERCIALIZAÇÃO)
    head = text.split("TARIFA DE COMERCIALIZAÇÃO")[0]
    for match in LADDER_RE.finditer(head):
        kva = match["kva"].replace(",", ".").rstrip("0").rstrip(".")
        kva = {"3.45": "3.45", "4.6": "4.6", "5.75": "5.75", "6.9": "6.9"}[kva]
        ladder[kva] = pt_number(match["power"])
        simples[kva] = pt_number(match["simples"])
        bi[kva] = (pt_number(match["fora"]), pt_number(match["vazio"]))
    if set(ladder) != {"3.45", "4.6", "5.75", "6.9"}:
        raise ParseFailed(f"galp: ladder rows missing, got {sorted(ladder)}")

    # Gas sale prices are the FIRST escalão table (the comercialização and
    # access breakdowns repeat the same row shape later in the document).
    gas_section = text.split("Gás Natural", 1)[-1]
    gas: dict[str, tuple[float, float]] = {}
    for match in GAS_RE.finditer(gas_section):
        gas.setdefault(
            match["tier"], (pt_number(match["fixed"]), pt_number(match["energy"]))
        )
    if set(gas) < {"1", "2"}:
        raise ParseFailed(f"galp: gas escalões missing, got {sorted(gas)}")

    fora, vazio = bi["4.6"]
    return {
        "electricity/galp-simples.yaml": {
            **{f"power:{k}": v for k, v in ladder.items()},
            "simples_total": simples["4.6"],
            "bi_fora_vazio": fora,
            "bi_vazio": vazio,
        },
        "gas/galp-gas.yaml": {
            "tier1_fixed": gas["1"][0],
            "tier1_energy": gas["1"][1],
            "tier2_fixed": gas["2"][0],
            "tier2_energy": gas["2"][1],
        },
    }
