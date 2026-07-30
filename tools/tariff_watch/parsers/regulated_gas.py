"""Regulated gas tariff (SU Gás) from tiagofelicia.pt's ERSE table copy.

The electricity twin of this page renders its prices with JavaScript, so
only gas is parseable statically; the regulated electricity seed changes
once a year and carries a valid_to that flags staleness instead.
"""

import re

from tools.tariff_watch.base import ParseFailed, pt_number, strip_html

URL = "https://www.tiagofelicia.pt/tarifa-regulada-gas-natural"

ROW = re.compile(
    r"Escalão (?P<tier>[12]) [\d —]+ (?P<fixed>\d,\d{4}) (?P<energy>\d,\d{4})"
)


def parse(html_bytes: bytes) -> dict:
    text = strip_html(html_bytes.decode("utf-8", errors="replace"))
    tiers: dict[str, tuple[float, float]] = {}
    for match in ROW.finditer(text):
        tiers[match["tier"]] = (pt_number(match["fixed"]), pt_number(match["energy"]))
    if set(tiers) < {"1", "2"}:
        raise ParseFailed(f"regulated gas: escalões incomplete ({sorted(tiers)})")
    return {
        "gas/su-gas.yaml": {
            "tier1_fixed": tiers["1"][0],
            "tier1_energy": tiers["1"][1],
            "tier2_fixed": tiers["2"][0],
            "tier2_energy": tiers["2"][1],
        }
    }
