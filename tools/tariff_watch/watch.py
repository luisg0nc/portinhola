"""Change detection for sources we deliberately don't parse.

The watch list is derived from the seeds themselves: every http(s)
source_url in tariffs/**.yaml that no parser claims. For each page we
hash the multiset of price-like tokens — a hash change means a number on
the page moved; copy edits and ad churn don't fire it.
"""

import hashlib
import re

import yaml

from tools.tariff_watch.base import TARIFFS_DIR, fetch, strip_html

PRICE_TOKEN = re.compile(r"\d+[.,]\d{2,6}")


def watched_urls(parsed_urls: set[str]) -> dict[str, list[str]]:
    """url -> list of tariff files citing it."""
    out: dict[str, list[str]] = {}
    for path in sorted(TARIFFS_DIR.rglob("*.yaml")):
        if path.name == "taxes.yaml":
            continue
        data = yaml.safe_load(path.read_text())
        url = str(data.get("source_url", ""))
        if url.startswith("http") and url not in parsed_urls:
            out.setdefault(url, []).append(str(path.relative_to(TARIFFS_DIR)))
    return out


def price_fingerprint(html: str) -> str:
    tokens = sorted(PRICE_TOKEN.findall(strip_html(html)))
    return hashlib.sha256("|".join(tokens).encode()).hexdigest()


def check(url: str, previous: str | None) -> tuple[str, bool]:
    """Returns (new_hash, changed)."""
    fingerprint = price_fingerprint(fetch(url).decode("utf-8", errors="replace"))
    return fingerprint, previous is not None and fingerprint != previous
