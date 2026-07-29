"""Fetch consumption from E-Redes by replaying a user-supplied cURL.

The portal login is reCAPTCHA-protected and cannot be automated
server-side, so the user pastes a "Copy as cURL" of the export request
(captured in their own browser). This module replays that request with
httpx — no browser — auto-advancing its date range and refreshing the
session cookies on use. All portal specifics live in `eredes_curl`.
"""

import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from portinhola.integrations.eredes_curl import is_expired, replay, substitute_dates
from portinhola.integrations.eredes_session import load_template, update_cookies
from portinhola.integrations.eredes_xlsx import IntervalRow, parse_eredes_xlsx


class SessionExpiredError(Exception):
    """The saved session no longer authenticates."""


def parse_eredes_json(content: bytes) -> list[IntervalRow]:
    # Pinned at discovery (Task 7). The XLSX export path is the expected one.
    raise NotImplementedError("e-redes json response shape pinned in Task 7")


def fetch_consumption(
    db: Session, app_key: bytes, cpe: str, date_from: date, date_to: date
) -> list[IntervalRow]:
    template = load_template(db, app_key)
    if template is None:
        raise SessionExpiredError()
    request = substitute_dates(template, date_from, date_to)
    result = replay(request)
    if is_expired(result):
        raise SessionExpiredError()
    update_cookies(db, app_key, result.set_cookies)

    if "json" in result.content_type.lower():
        return parse_eredes_json(result.content)
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "export.xlsx"
        target.write_bytes(result.content)
        return parse_eredes_xlsx(target).rows


def utc_today() -> date:
    return datetime.now(UTC).date()
