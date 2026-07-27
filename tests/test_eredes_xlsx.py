from datetime import UTC, datetime
from pathlib import Path

import openpyxl
import pytest

from portinhola.integrations.eredes_xlsx import parse_eredes_xlsx

SAMPLE_DIR = Path("/home/luisgonc/projects/portinhola/sample-eredes")


def _monthly_workbook(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Dados Globais"])
    ws.append([])
    ws.append(["CPE", "PT000TESTCPE"])
    ws.append(["Funções", "Consumo registado"])
    ws.append(["", "Estado"])
    ws.append(["Mês/Ano", "julho 2026"])
    ws.append(["Intervalo:", "15 min"])
    ws.append([])
    ws.append(["Data", "Hora", "Consumo registado (kW)", "Estado"])
    for row in rows:
        ws.append(list(row))
    wb.save(path)


def _range_workbook(path: Path, rows: list[tuple[str, str, str, str, str]]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Dados Globais", None, None, None, None])
    ws.append([None, None, None, None, None])
    ws.append(["CPE", "PT000TESTCPE", None, None, None])
    ws.append(["Data de Início", "2026-06-01", None, None, None])
    ws.append(["Data de Fim", "2026-06-02", None, None, None])
    ws.append(["Intervalo", "15 min", None, None, None])
    ws.append([None, None, None, None, None])
    ws.append(["Contador", "Data", "Hora", "Consumo registado, Ativa (kW)", "Estado"])
    for row in rows:
        ws.append(list(row))
    wb.save(path)


def test_monthly_layout_basic(tmp_path) -> None:
    path = tmp_path / "monthly.xlsx"
    _monthly_workbook(
        path,
        [
            ("2026/07/01", "00:15", "0,632", "Real"),
            ("2026/07/01", "00:30", "0,516", "Estimado"),
        ],
    )
    result = parse_eredes_xlsx(path)
    assert result.cpe == "PT000TESTCPE"
    assert len(result.rows) == 2
    # July: Lisbon is UTC+1 → local 00:00 slot start = 23:00 UTC previous day
    ts, kwh, quality = result.rows[0]
    assert ts == datetime(2026, 6, 30, 23, 0, tzinfo=UTC)
    assert kwh == pytest.approx(0.632 / 4)
    assert quality == "real"
    assert result.rows[1][2] == "estimated"


def test_midnight_end_belongs_to_previous_day(tmp_path) -> None:
    path = tmp_path / "midnight.xlsx"
    _monthly_workbook(path, [("2026/07/02", "00:00", "0,4", "Real")])
    result = parse_eredes_xlsx(path)
    ts, _, _ = result.rows[0]
    # local end 2026-07-02 00:00 → start 2026-07-01 23:45 local → 22:45 UTC
    assert ts == datetime(2026, 7, 1, 22, 45, tzinfo=UTC)


def test_range_layout_with_contador_column(tmp_path) -> None:
    path = tmp_path / "range.xlsx"
    _range_workbook(
        path,
        [
            ("000002100000000", "2026/06/01", "00:15", "0,188", "Real"),
            ("000002100000000", "2026/06/01", "00:30", "0,2", "Real"),
        ],
    )
    result = parse_eredes_xlsx(path)
    assert result.cpe == "PT000TESTCPE"
    assert len(result.rows) == 2
    assert result.rows[0][1] == pytest.approx(0.188 / 4)


def test_winter_time_offset(tmp_path) -> None:
    path = tmp_path / "winter.xlsx"
    _monthly_workbook(path, [("2026/01/15", "10:15", "1,0", "Real")])
    result = parse_eredes_xlsx(path)
    ts, _, _ = result.rows[0]
    # January: Lisbon == UTC → local slot start 10:00 == 10:00 UTC
    assert ts == datetime(2026, 1, 15, 10, 0, tzinfo=UTC)


@pytest.mark.skipif(not SAMPLE_DIR.exists(), reason="real exports only on owner machine")
def test_real_exports_parse() -> None:
    files = sorted(SAMPLE_DIR.glob("*.xlsx"))
    assert files
    for f in files:
        result = parse_eredes_xlsx(f)
        assert result.cpe is not None and result.cpe.startswith("PT")
        assert len(result.rows) > 1000
        timestamps = [r[0] for r in result.rows]
        assert len(set(timestamps)) == len(timestamps), f"duplicate slots in {f.name}"
