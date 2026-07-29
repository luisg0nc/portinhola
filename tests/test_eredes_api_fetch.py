import io
from datetime import date

import openpyxl
import pytest

from portinhola.integrations.eredes_api import SessionExpiredError, fetch_consumption
from portinhola.integrations.eredes_curl import CurlRequest, ReplayResult
from portinhola.integrations.eredes_session import load_template, save_template

KEY = b"k" * 32


def _template() -> CurlRequest:
    return CurlRequest(
        method="GET",
        url="https://balcaodigital.e-redes.pt/api/export?startDate=2026-06-01&endDate=2026-07-01",
        headers={},
        cookies={"PHPSESSID": "old"},
        body=None,
    )


def _xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Dados Globais"])
    ws.append([])
    ws.append(["CPE", "PT1"])
    ws.append(["Funções", "Consumo registado"])
    ws.append(["", "Estado"])
    ws.append(["Mês/Ano", "julho 2026"])
    ws.append(["Intervalo:", "15 min"])
    ws.append([])
    ws.append(["Data", "Hora", "Consumo registado (kW)", "Estado"])
    ws.append(["2026/07/01", "00:15", "0,4", "Real"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_fetch_no_template_raises(app) -> None:
    with app.state.sessionmaker() as db, pytest.raises(SessionExpiredError):
        fetch_consumption(db, KEY, "PT1", date(2026, 7, 1), date(2026, 7, 2))


def test_fetch_replays_and_parses(app, monkeypatch) -> None:
    xlsx = _xlsx_bytes()

    def fake_replay(req):
        assert "startDate=2026-07-01" in req.url  # dates substituted
        return ReplayResult(
            status=200,
            content=xlsx,
            content_type="application/vnd.ms-excel",
            set_cookies={"PHPSESSID": "new99"},
        )

    monkeypatch.setattr("portinhola.integrations.eredes_api.replay", fake_replay)
    with app.state.sessionmaker() as db:
        save_template(db, KEY, _template())
        rows = fetch_consumption(db, KEY, "PT1", date(2026, 7, 1), date(2026, 7, 2))
        assert len(rows) == 1
        loaded = load_template(db, KEY)
        assert loaded is not None
        assert loaded.cookies["PHPSESSID"] == "new99"  # cookie refreshed


def test_fetch_expired_raises(app, monkeypatch) -> None:
    monkeypatch.setattr(
        "portinhola.integrations.eredes_api.replay",
        lambda req: ReplayResult(status=401, content=b"", content_type="", set_cookies={}),
    )
    with app.state.sessionmaker() as db:
        save_template(db, KEY, _template())
        with pytest.raises(SessionExpiredError):
            fetch_consumption(db, KEY, "PT1", date(2026, 7, 1), date(2026, 7, 2))
