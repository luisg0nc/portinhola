from datetime import date

import pytest

from portinhola.integrations.eredes_curl import (
    CurlRequest,
    CurlValidationError,
    parse_curl,
    read_expiry,
    substitute_dates,
    validate,
)

CHROME_CURL = r"""curl 'https://balcaodigital.e-redes.pt/api/consumptions/export?cpe=PT0002000000000000XX&startDate=2026-06-01&endDate=2026-07-01' \
  -H 'accept: application/json' \
  -H 'authorization: Bearer abc.def.ghi' \
  -b 'PHPSESSID=sess123; aat=tok456' \
  --compressed"""


def test_parse_basic_get() -> None:
    req = parse_curl(CHROME_CURL)
    assert isinstance(req, CurlRequest)
    assert req.method == "GET"
    assert req.url.startswith("https://balcaodigital.e-redes.pt/api/consumptions/export")
    assert req.headers["authorization"] == "Bearer abc.def.ghi"
    assert req.cookies == {"PHPSESSID": "sess123", "aat": "tok456"}
    assert req.body is None


def test_data_flag_implies_post() -> None:
    curl = (
        "curl 'https://balcaodigital.e-redes.pt/api/x' "
        "-H 'content-type: application/json' "
        "--data-raw '{\"startDate\":\"2026-06-01\"}'"
    )
    req = parse_curl(curl)
    assert req.method == "POST"
    assert req.body == '{"startDate":"2026-06-01"}'


def test_cookie_header_merged() -> None:
    curl = "curl 'https://balcaodigital.e-redes.pt/api/x' -H 'Cookie: a=1; b=2'"
    req = parse_curl(curl)
    assert req.cookies == {"a": "1", "b": "2"}
    assert "cookie" not in {k.lower() for k in req.headers}


def test_dollar_quoted_cookie() -> None:
    curl = "curl 'https://balcaodigital.e-redes.pt/api/x' -b $'k=v\\tx'"
    req = parse_curl(curl)
    assert req.cookies["k"].startswith("v")


def test_rejects_non_curl() -> None:
    with pytest.raises(CurlValidationError) as exc:
        parse_curl("not a curl command")
    assert exc.value.reason == "not_curl"


def _req(url: str, body: str | None = None, headers=None):
    return CurlRequest(
        method="GET", url=url, headers=headers or {}, cookies={}, body=body
    )


def test_validate_accepts_e_redes_with_dates() -> None:
    validate(_req("https://balcaodigital.e-redes.pt/api/x?s=2026-06-01&e=2026-07-01"))


def test_validate_rejects_wrong_host() -> None:
    with pytest.raises(CurlValidationError) as exc:
        validate(_req("https://evil.example.com/api/x?s=2026-06-01&e=2026-07-01"))
    assert exc.value.reason == "wrong_host"


def test_validate_rejects_no_dates() -> None:
    with pytest.raises(CurlValidationError) as exc:
        validate(_req("https://balcaodigital.e-redes.pt/api/x"))
    assert exc.value.reason == "no_date_range"


def test_substitute_dates_query() -> None:
    req = _req("https://balcaodigital.e-redes.pt/api/x?startDate=2026-06-01&endDate=2026-07-01")
    out = substitute_dates(req, date(2026, 1, 5), date(2026, 1, 20))
    assert "startDate=2026-01-05" in out.url
    assert "endDate=2026-01-20" in out.url


def test_substitute_dates_body() -> None:
    req = _req(
        "https://balcaodigital.e-redes.pt/api/x",
        body='{"startDate":"2026-06-01","endDate":"2026-07-01"}',
    )
    out = substitute_dates(req, date(2026, 1, 5), date(2026, 1, 20))
    assert out.body == '{"startDate":"2026-01-05","endDate":"2026-01-20"}'


def test_read_expiry_from_jwt() -> None:
    import base64
    import json

    payload = base64.urlsafe_b64encode(json.dumps({"exp": 946684800}).encode()).decode().rstrip("=")
    jwt = f"h.{payload}.s"
    req = _req("https://balcaodigital.e-redes.pt/api/x?s=2026-06-01&e=2026-07-01",
               headers={"authorization": f"Bearer {jwt}"})
    got = read_expiry(req)
    assert got is not None
    assert got.year == 2000


def test_read_expiry_none_without_jwt() -> None:
    assert read_expiry(_req("https://balcaodigital.e-redes.pt/api/x?s=2026-06-01&e=2026-07-01")) is None
