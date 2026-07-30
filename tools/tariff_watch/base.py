"""Shared plumbing for the tariff watcher/parsers."""

import re
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).parent.parent.parent
TARIFFS_DIR = REPO_ROOT / "tariffs"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) portinhola-tariff-watch "
    "(+https://github.com/luisg0nc/portinhola)"
)


class ParseFailed(Exception):
    """A source no longer matches the expected layout — never guess."""


def fetch(url: str) -> bytes:
    response = httpx.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True
    )
    response.raise_for_status()
    return response.content


def strip_html(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def pt_number(token: str) -> float:
    return float(token.replace(".", "").replace(",", "."))
