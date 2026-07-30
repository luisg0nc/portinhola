"""Goldenergy official reference-price page → goldenergy yamls.

The Tarifário Digital tables list, per kVA row, the potência and the
energy at each discount level; the last energy column is the 12%
(e-invoice + direct debit) price our seeds use. Energy gets the
social-tariff financing surcharge Goldenergy lists separately. Gas uses
the Preço Base row.
"""

import re

from tools.tariff_watch.base import ParseFailed, pt_number, strip_html

URL = "https://goldenergy.pt/precos-de-referencia/"

SOCIAL_SURCHARGE = 0.0020666  # €/kWh, financiamento da tarifa social

SIMPLES_ROW = re.compile(
    r"(?P<kva>3,45|4,6|5,75|6,9) (?P<power>\d,\d{4})"
    r"(?: \d,\d{4}){3} (?P<energy>\d,\d{4})"
)
BI_ROW = re.compile(
    r"(?P<kva>3,45|4,6|5,75|6,9) (?P<power>\d,\d{4})"
    r"(?: \d,\d{4}){6} (?P<fora>\d,\d{4}) (?P<vazio>\d,\d{4})"
)
GAS_BASE = re.compile(
    r"Preço Base (?P<e1>\d,\d{4}) (?P<e2>\d,\d{4}) \d,\d{4} \d,\d{4} "
    r"(?P<f1>\d,\d{4}) (?P<f2>\d,\d{4})"
)


def parse(html_bytes: bytes) -> dict:
    text = strip_html(html_bytes.decode("utf-8", errors="replace"))

    ladder: dict[str, float] = {}
    simples_energy: float | None = None
    for match in SIMPLES_ROW.finditer(text):
        kva = match["kva"].replace(",", ".")
        ladder.setdefault(kva, pt_number(match["power"]))
        if simples_energy is None:
            simples_energy = pt_number(match["energy"])
    if set(ladder) != {"3.45", "4.6", "5.75", "6.9"} or simples_energy is None:
        raise ParseFailed(f"goldenergy: simples table incomplete ({sorted(ladder)})")

    bi_match = BI_ROW.search(text)
    if bi_match is None:
        raise ParseFailed("goldenergy: bi-horária row not found")
    fora = pt_number(bi_match["fora"])
    vazio = pt_number(bi_match["vazio"])

    gas_match = GAS_BASE.search(text)
    if gas_match is None:
        raise ParseFailed("goldenergy: gas Preço Base row not found")

    return {
        "electricity/goldenergy-simples.yaml": {
            **{f"power:{k}": v for k, v in ladder.items()},
            "simples_total": round(simples_energy + SOCIAL_SURCHARGE, 4),
            "bi_fora_vazio": round(fora + SOCIAL_SURCHARGE, 4),
            "bi_vazio": round(vazio + SOCIAL_SURCHARGE, 4),
        },
        "gas/goldenergy-gas.yaml": {
            "tier1_fixed": pt_number(gas_match["f1"]),
            "tier1_energy": pt_number(gas_match["e1"]),
            "tier2_fixed": pt_number(gas_match["f2"]),
            "tier2_energy": pt_number(gas_match["e2"]),
        },
    }
