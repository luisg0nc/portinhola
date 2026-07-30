"""Patch tariff YAMLs in place, preserving provenance comments.

Parsers emit updates keyed by a small vocabulary; each key maps to an
anchored regex. An anchor that doesn't match raises — the file layout is
part of the contract, and a miss means a human restructured the YAML.
"""

import re
from datetime import date
from pathlib import Path

from tools.tariff_watch.base import ParseFailed


def _sub_once(text: str, pattern: str, value: float, occurrence: int = 1) -> str:
    matches = list(re.finditer(pattern, text))
    if len(matches) < occurrence:
        raise ParseFailed(f"anchor {pattern!r} (#{occurrence}) not found")
    match = matches[occurrence - 1]
    if abs(float(match.group(2)) - value) < 1e-9:
        return text  # same price — keep the existing formatting untouched
    return text[: match.start(2)] + f"{value:g}" + text[match.end(2) :]


def apply_updates(yaml_path: Path, updates: dict[str, float], today: date) -> bool:
    """Returns True when the file content changed."""
    original = yaml_path.read_text()
    text = original
    for key, value in updates.items():
        if key.startswith("power:"):
            kva = key.split(":", 1)[1]
            text = _sub_once(text, rf'("{re.escape(kva)}"): ([0-9.]+)', value)
        elif key == "simples_total":
            text = _sub_once(text, r"(total): ([0-9.]+)", value)
        elif key == "bi_vazio":
            text = _sub_once(text, r"(vazio): ([0-9.]+)", value)
        elif key == "bi_fora_vazio":
            text = _sub_once(text, r"(fora_vazio): ([0-9.]+)", value)
        elif key in ("tier1_fixed", "tier2_fixed"):
            occurrence = 1 if key.startswith("tier1") else 2
            text = _sub_once(text, r"(fixed_eur_day): ([0-9.]+)", value, occurrence)
        elif key in ("tier1_energy", "tier2_energy"):
            occurrence = 1 if key.startswith("tier1") else 2
            text = _sub_once(text, r"(energy_eur_kwh): ([0-9.]+)", value, occurrence)
        else:
            raise ParseFailed(f"unknown update key {key!r}")
    if text != original:
        text = re.sub(
            r"(retrieved): (\d{4}-\d{2}-\d{2})",
            rf"\1: {today.isoformat()}",
            text,
            count=1,
        )
        yaml_path.write_text(text)
        return True
    return False
