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

import httpx
from sqlalchemy.orm import Session

from portinhola.integrations.eredes_session import load_token, save_token
from portinhola.integrations.eredes_xlsx import IntervalRow

BASE_URL = "https://balcaodigital.e-redes.pt"
CONSUMPTION_ENDPOINT = "/ms/reading/data-usage/edm/get"
ACTIVE_ENERGY_REGISTER = "A+"

# Test seam: tests set this to an httpx.MockTransport; production is None.
_transport_for_tests: httpx.MockTransport | None = None


class SessionExpiredError(Exception):
    """The saved `aat` token no longer authenticates."""


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

    `loadCurveTimestamp` is an ISO-8601 UTC instant marking the END of the
    15-minute slot; we store the slot START (end − 15 min) to match the
    XLSX importer's convention so file-import and API-sync dedupe cleanly.
    `meterLoadCurve` is already energy in kWh for the slot.
    """
    result = (data or {}).get("Body", {}).get("Result", {})
    rows: list[IntervalRow] = []
    seen: set[datetime] = set()
    for device in result.get("utilitiesDevices", []) or []:
        for meter in device.get("meterLoadCurves", []) or []:
            if meter.get("register") != ACTIVE_ENERGY_REGISTER:
                continue
            for point in meter.get("loadCurves", []) or []:
                ts_raw = point.get("loadCurveTimestamp")
                value = point.get("meterLoadCurve")
                if ts_raw is None or value is None:
                    continue
                end = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
                start = end - timedelta(minutes=15)
                if start in seen:
                    continue
                seen.add(start)
                rows.append((start, float(value), "real"))
    rows.sort(key=lambda r: r[0])
    return rows


def fetch_consumption(
    db: Session, app_key: bytes, cpe: str, date_from: date, date_to: date
) -> list[IntervalRow]:
    token = load_token(db, app_key)
    if not token:
        raise SessionExpiredError()
    with httpx.Client(timeout=120.0, transport=_transport_for_tests) as client:
        response = client.post(
            f"{BASE_URL}{CONSUMPTION_ENDPOINT}",
            json=_body(cpe, date_from, date_to),
            headers=_headers(token),
        )
    if response.status_code in (401, 403):
        raise SessionExpiredError()
    response.raise_for_status()
    # The portal may hand back a refreshed aat cookie; keep the session alive.
    refreshed = response.cookies.get("aat")
    if refreshed and refreshed != token:
        save_token(db, app_key, refreshed)
    return parse_response(response.json())


def utc_today() -> date:
    return datetime.now(UTC).date()
