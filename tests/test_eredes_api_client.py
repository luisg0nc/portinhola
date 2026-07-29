from datetime import UTC, date, datetime

import httpx
import pytest

import portinhola.integrations.eredes_api as mod
from portinhola.integrations.eredes_api import (
    SessionExpiredError,
    fetch_consumption,
    parse_response,
)
from portinhola.integrations.eredes_session import load_token, save_token

KEY = b"k" * 32


SAMPLE = {
    "Body": {
        "Success": True,
        "Result": {
            "utilitiesDevices": [
                {
                    "meterLoadCurves": [
                        {
                            "register": "A+",
                            "loadCurves": [
                                {
                                    "loadCurveTimestamp": "2026-01-05T00:15:00Z",
                                    "meterLoadCurve": 0.052,
                                    "meterLoadCurveUnitMeasurement": "kwh",
                                },
                                {
                                    "loadCurveTimestamp": "2026-01-05T00:30:00Z",
                                    "meterLoadCurve": 0.06,
                                    "meterLoadCurveUnitMeasurement": "kwh",
                                },
                            ],
                        },
                        {
                            "register": "A-",
                            "loadCurves": [
                                {
                                    "loadCurveTimestamp": "2026-01-05T00:15:00Z",
                                    "meterLoadCurve": 99.0,
                                    "meterLoadCurveUnitMeasurement": "kwh",
                                }
                            ],
                        },
                    ]
                }
            ]
        },
    }
}


def test_parse_response_active_energy_only() -> None:
    rows = parse_response(SAMPLE)
    assert len(rows) == 2  # A- ignored
    # first slot: end 00:15 UTC -> start 00:00 UTC
    assert rows[0] == (datetime(2026, 1, 5, 0, 0, tzinfo=UTC), 0.052, "real")
    assert rows[1][0] == datetime(2026, 1, 5, 0, 15, tzinfo=UTC)


def test_parse_empty_result() -> None:
    assert parse_response({"Body": {"Result": {}}}) == []


def test_fetch_no_token_raises(app) -> None:
    with app.state.sessionmaker() as db, pytest.raises(SessionExpiredError):
        fetch_consumption(db, KEY, "PT1", date(2026, 1, 5), date(2026, 1, 6))


def test_fetch_posts_and_parses(app, monkeypatch) -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["cookie"] = request.headers.get("cookie")
        captured["authreq"] = request.headers.get("authorization-request")
        import json

        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=SAMPLE)

    monkeypatch.setattr(mod, "_transport_for_tests", httpx.MockTransport(handler))
    with app.state.sessionmaker() as db:
        save_token(db, KEY, "tok123")
        rows = fetch_consumption(db, KEY, "PT1CPE", date(2026, 1, 5), date(2026, 1, 6))
    assert len(rows) == 2
    assert captured["url"].endswith("/ms/reading/data-usage/edm/get")
    assert "aat=tok123" in captured["cookie"]
    assert captured["authreq"] == "tok123"
    assert captured["body"]["cpe"] == "PT1CPE"
    assert captured["body"]["request_type"] == "3"
    assert captured["body"]["start_date"] == "2026-01-05 00:00:00"
    assert captured["body"]["end_date"] == "2026-01-06 23:59:59"


def test_fetch_401_raises_expired(app, monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_transport_for_tests",
        httpx.MockTransport(lambda req: httpx.Response(401, json={})),
    )
    with app.state.sessionmaker() as db:
        save_token(db, KEY, "tok123")
        with pytest.raises(SessionExpiredError):
            fetch_consumption(db, KEY, "PT1", date(2026, 1, 5), date(2026, 1, 6))


def test_fetch_refreshes_token_from_cookie(app, monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=SAMPLE, headers={"set-cookie": "aat=refreshed99; Path=/"}
        )

    monkeypatch.setattr(mod, "_transport_for_tests", httpx.MockTransport(handler))
    with app.state.sessionmaker() as db:
        save_token(db, KEY, "old")
        fetch_consumption(db, KEY, "PT1", date(2026, 1, 5), date(2026, 1, 6))
        assert load_token(db, KEY) == "refreshed99"
