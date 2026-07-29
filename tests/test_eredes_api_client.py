from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

import portinhola.integrations.eredes_api as mod
from portinhola.integrations.eredes_api import (
    EredesFetchError,
    SessionExpiredError,
    fetch_consumption,
    parse_response,
)
from portinhola.integrations.eredes_session import save_token

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
                                    "loadCurveTimestamp": "2026-01-05T00:00:00Z",
                                    "meterLoadCurve": 0.052,
                                    "meterLoadCurveUnitMeasurement": "kwh",
                                },
                                {
                                    "loadCurveTimestamp": "2026-01-05T00:15:00Z",
                                    "meterLoadCurve": 0.06,
                                    "meterLoadCurveUnitMeasurement": "kwh",
                                },
                            ],
                        },
                        {
                            "register": "A-",
                            "loadCurves": [
                                {
                                    "loadCurveTimestamp": "2026-01-05T00:00:00Z",
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
    # END in Lisbon local (Jan == UTC), minus 15 min -> START.
    # 00:00 end -> 2026-01-04 23:45 UTC start; 00:15 end -> 00:00 UTC start.
    assert rows[0] == (datetime(2026, 1, 4, 23, 45, tzinfo=UTC), 0.052, "real")
    assert rows[1][0] == datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def test_parse_response_summer_local_to_utc() -> None:
    # July: Lisbon UTC+1. End 00:00 local -> 2026-06-30 23:00 UTC end
    # -> 2026-06-30 22:45 UTC start.
    summer = {
        "Body": {
            "Result": {
                "utilitiesDevices": [
                    {
                        "meterLoadCurves": [
                            {
                                "register": "A+",
                                "loadCurves": [
                                    {
                                        "loadCurveTimestamp": "2026-07-01T00:00:00Z",
                                        "meterLoadCurve": 0.077,
                                        "meterLoadCurveUnitMeasurement": "kwh",
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }
        }
    }
    rows = parse_response(summer)
    assert rows[0][0] == datetime(2026, 6, 30, 22, 45, tzinfo=UTC)


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


def test_parse_response_tolerates_null_result() -> None:
    # A rejected window really does come back as Success:false / Result:null.
    assert parse_response({"Body": {"Success": False, "Result": None}}) == []
    assert parse_response({}) == []


def test_fetch_chunks_wide_ranges(app, monkeypatch) -> None:
    """A year in one request returns Result:null from the portal, so the
    client must split it into <=31-day windows."""
    windows: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        b = json.loads(request.content)
        windows.append((b["start_date"][:10], b["end_date"][:10]))
        return httpx.Response(200, json=SAMPLE)

    monkeypatch.setattr(mod, "_transport_for_tests", httpx.MockTransport(handler))
    with app.state.sessionmaker() as db:
        save_token(db, KEY, "tok")
        fetch_consumption(db, KEY, "PT1", date(2026, 1, 1), date(2026, 3, 31))

    assert len(windows) == 3  # 90 days -> 31 + 31 + 28
    assert windows[0] == ("2026-01-01", "2026-01-31")
    assert windows[-1][1] == "2026-03-31"
    # windows are contiguous and never exceed the cap
    for (_, prev_end), (next_start, _) in zip(windows, windows[1:], strict=False):
        assert date.fromisoformat(next_start) == date.fromisoformat(prev_end) + timedelta(
            days=1
        )


def test_fetch_raises_when_every_window_empty(app, monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "_transport_for_tests",
        httpx.MockTransport(
            lambda req: httpx.Response(200, json={"Body": {"Success": False, "Result": None}})
        ),
    )
    with app.state.sessionmaker() as db:
        save_token(db, KEY, "tok")
        with pytest.raises(EredesFetchError):
            fetch_consumption(db, KEY, "PT1", date(2026, 1, 1), date(2026, 1, 5))
