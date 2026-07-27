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


def fetch_consumption(
    cookies: list[dict], cpe: str, date_from: date, date_to: date
) -> list[IntervalRow]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)  # type: ignore[arg-type]
        page = context.new_page()
        try:
            page.goto(CONSUMPTION_URL, timeout=PAGE_TIMEOUT_MS)
            page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT_MS)
            if LOGIN_URL_MARKER in page.url.lower():
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
            browser.close()


def utc_today() -> date:
    return datetime.now(UTC).date()
