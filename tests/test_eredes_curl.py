import pytest

from portinhola.integrations.eredes_curl import (
    CurlRequest,
    CurlValidationError,
    parse_curl,
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
