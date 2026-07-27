"""Fetch consumption from the E-Redes Balcão Digital using a saved session.

Strategy: drive the portal with Playwright (cookies restored from the
assisted login), open the consumption-history page for the CPE, request the
XLSX export for the wanted date range, download it, and reuse
`parse_eredes_xlsx`. All portal-specific selectors live in this file so a
portal change is a one-file fix.

NOTE: the selector constants below are finalized during the live end-to-end
pass (Plan 3 Task 11) against the real portal; the module structure and the
error contract are stable.
"""

import tempfile
import time
from datetime import UTC, date, datetime
from pathlib import Path

from portinhola.integrations.eredes_xlsx import IntervalRow, parse_eredes_xlsx


class SessionExpiredError(Exception):
    """The saved session no longer authenticates (redirected to login)."""


CONSUMPTION_URL = "https://balcaodigital.e-redes.pt/consumptions/history"
LOGIN_URL_MARKER = "login"
# Selectors pinned during live discovery (Task 11):
SEL_DATE_FROM = "input[name='dateFrom']"
SEL_DATE_TO = "input[name='dateTo']"
SEL_EXPORT_XLSX = "text=Exportar excel"
PAGE_TIMEOUT_MS = 60_000


COOKIE_FIELDS = ("name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite")


def _extend_session_cookies(cookies: list[dict]) -> list[dict]:
    """Session cookies die with the login browser; give them 30 days so the
    replayed context still authenticates."""
    prepared = []
    for cookie in cookies:
        item = {k: v for k, v in cookie.items() if k in COOKIE_FIELDS}
        if item.get("expires", -1) in (-1, None) or item.get("expires", 0) < time.time():
            item["expires"] = time.time() + 30 * 86400
        prepared.append(item)
    return prepared


def fetch_consumption(
    profile_dir: Path, cookies: list[dict], cpe: str, date_from: date, date_to: date
) -> list[IntervalRow]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(profile_dir),
            headless=True,
            channel="chromium",
            args=["--disable-blink-features=AutomationControlled"],
            locale="pt-PT",
            timezone_id="Europe/Lisbon",
        )
        context.add_cookies(_extend_session_cookies(cookies))  # type: ignore[arg-type]
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(CONSUMPTION_URL, timeout=PAGE_TIMEOUT_MS)
            page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
            if LOGIN_URL_MARKER in page.url.lower():
                raise SessionExpiredError()
            body = page.inner_text("body")
            if "Validação de Segurança" in body:
                raise SessionExpiredError()

            page.fill(SEL_DATE_FROM, date_from.strftime("%Y-%m-%d"))
            page.fill(SEL_DATE_TO, date_to.strftime("%Y-%m-%d"))
            with page.expect_download(timeout=PAGE_TIMEOUT_MS) as download_info:
                page.click(SEL_EXPORT_XLSX)
            download = download_info.value
            with tempfile.TemporaryDirectory() as tmp_dir:
                target = Path(tmp_dir) / "export.xlsx"
                download.save_as(target)
                export = parse_eredes_xlsx(target)
            return export.rows
        finally:
            context.close()


def utc_today() -> date:
    return datetime.now(UTC).date()
