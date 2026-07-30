"""Fetch consumption from E-Redes Balcão Digital using the user's `aat`
session token.

The portal login is reCAPTCHA-protected and cannot be automated
server-side, so the user copies the `aat` cookie value from their own
browser (DevTools → Application → Cookies). This module calls the same
internal endpoint the portal's SPA uses, authenticated with that token —
no browser, no reCAPTCHA. Endpoint/shape mirror the community
`ha-eredes` integration (github.com/mrfyda/ha-eredes).
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from portinhola.integrations.eredes_session import load_token
from portinhola.integrations.eredes_xlsx import IntervalRow

BASE_URL = "https://balcaodigital.e-redes.pt"
CONSUMPTION_ENDPOINT = "/ms/reading/data-usage/edm/get"
ACTIVE_ENERGY_REGISTER = "A+"
LISBON = ZoneInfo("Europe/Lisbon")

# The portal is unreliable on wide ranges: a 365-day request comes back
# `Success: false, Result: null` while ~31-day windows are consistently
# fine. Fetch in chunks and retry each one before giving up on it.
MAX_CHUNK_DAYS = 31
CHUNK_ATTEMPTS = 2

# Test seam: tests set this to an httpx.MockTransport; production is None.
_transport_for_tests: httpx.MockTransport | None = None


class SessionExpiredError(Exception):
    """The saved `aat` token no longer authenticates."""


class EredesFetchError(Exception):
    """The portal answered, but returned no usable data for the range."""


def _headers(token: str) -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/consumptions/history",
        "User-Agent-Context": "WEB",
        "Show-Loader": "true",
        "Cookie": f"aat={token}",
        "Authorization-Request": token,
    }


def _body(cpe: str, date_from: date, date_to: date) -> dict:
    return {
        "cpe": cpe,
        "request_type": "3",  # 15-minute load curve
        "start_date": f"{date_from.isoformat()} 00:00:00",
        "end_date": f"{date_to.isoformat()} 23:59:59",
        "wait": True,
        "formatted": False,
        "nif_requester": None,
        "serial_number": "",
        "nif": None,
    }


def parse_response(data: dict) -> list[IntervalRow]:
    """Walk Body→Result→utilitiesDevices→meterLoadCurves→loadCurves.

    `loadCurveTimestamp` is the 15-minute slot END, and despite the trailing
    'Z' the portal reports it in Europe/Lisbon local time (both verified
    slot-for-slot against the owner's XLSX export). So we localize to
    Lisbon, convert to UTC, and subtract 15 min to get the slot START —
    matching the XLSX importer exactly so file-import and API-sync dedupe.
    `meterLoadCurve` is already energy in kWh for the slot.
    """
    # A rejected window returns {"Success": false, "Result": null}, so every
    # level here has to tolerate null.
    result = ((data or {}).get("Body") or {}).get("Result") or {}
    rows: list[IntervalRow] = []
    seen: set[datetime] = set()
    for device in result.get("utilitiesDevices") or []:
        for meter in device.get("meterLoadCurves") or []:
            if meter.get("register") != ACTIVE_ENERGY_REGISTER:
                continue
            for point in meter.get("loadCurves") or []:
                ts_raw = point.get("loadCurveTimestamp")
                value = point.get("meterLoadCurve")
                if ts_raw is None or value is None:
                    continue
                naive = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%SZ")  # noqa: DTZ007 - the "Z" lies; portal sends Lisbon local
                end_utc = naive.replace(tzinfo=LISBON).astimezone(UTC)
                start = end_utc - timedelta(minutes=15)
                if start in seen:
                    continue
                seen.add(start)
                rows.append((start, float(value), "real"))
    rows.sort(key=lambda r: r[0])
    return rows


def _chunks(date_from: date, date_to: date) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    start = date_from
    while start <= date_to:
        end = min(start + timedelta(days=MAX_CHUNK_DAYS - 1), date_to)
        out.append((start, end))
        start = end + timedelta(days=1)
    return out


def fetch_consumption(
    db: Session, app_key: bytes, cpe: str, date_from: date, date_to: date
) -> list[IntervalRow]:
    token = load_token(db, app_key)
    if not token:
        raise SessionExpiredError()

    merged: dict[datetime, IntervalRow] = {}
    failed: list[tuple[date, date]] = []
    with httpx.Client(timeout=180.0, transport=_transport_for_tests) as client:
        for chunk_from, chunk_to in _chunks(date_from, date_to):
            rows: list[IntervalRow] | None = None
            for _attempt in range(CHUNK_ATTEMPTS):
                response = client.post(
                    f"{BASE_URL}{CONSUMPTION_ENDPOINT}",
                    json=_body(cpe, chunk_from, chunk_to),
                    headers=_headers(token),
                )
                if response.status_code in (401, 403):
                    raise SessionExpiredError()
                response.raise_for_status()
                parsed = parse_response(response.json())
                if parsed:
                    rows = parsed
                    break
            if rows is None:
                failed.append((chunk_from, chunk_to))
                continue
            for row in rows:
                merged[row[0]] = row

    if failed and not merged:
        raise EredesFetchError(
            f"E-Redes returned no data for {len(failed)} window(s) "
            f"between {date_from} and {date_to}"
        )
    return [merged[ts] for ts in sorted(merged)]


def utc_today() -> date:
    return datetime.now(UTC).date()
