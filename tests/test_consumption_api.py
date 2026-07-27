from tests.test_eredes_xlsx import _monthly_workbook


def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


def _make_sp(client, identifier: str = "PT000TESTCPE") -> int:
    res = client.post(
        "/api/supply-points",
        json={"utility": "electricity", "identifier": identifier, "name": "Casa"},
    )
    return res.json()["id"]


def _import_file(client, tmp_path, sp_id: int, rows, force: bool = False):
    path = tmp_path / "import.xlsx"
    _monthly_workbook(path, rows)
    with open(path, "rb") as fh:
        return client.post(
            "/api/consumption/import",
            data={"supply_point_id": str(sp_id), "force": "true" if force else "false"},
            files={"file": ("import.xlsx", fh, "application/vnd.ms-excel")},
        )


def test_import_and_queries(client, tmp_path) -> None:
    _login(client)
    sp_id = _make_sp(client)
    rows = [
        (f"2026/07/0{day}", f"{h:02d}:15", "1,0", "Real")
        for day in (1, 2)
        for h in range(10, 14)
    ]
    res = _import_file(client, tmp_path, sp_id, rows)
    assert res.status_code == 200
    body = res.json()
    assert body["inserted"] == 8
    assert body["updated"] == 0

    day = client.get(f"/api/consumption/day?supply_point_id={sp_id}&date=2026-07-01").json()
    assert len(day) == 4
    assert day[0]["kwh"] == 0.25

    month = client.get(f"/api/consumption/month?supply_point_id={sp_id}&month=2026-07").json()
    assert len(month) == 2
    assert month[0] == {"date": "2026-07-01", "kwh": 1.0}

    year = client.get(f"/api/consumption/year?supply_point_id={sp_id}&year=2026").json()
    assert year == [{"month": "2026-07", "kwh": 2.0}]

    status = client.get(f"/api/consumption/status?supply_point_id={sp_id}").json()
    assert status["count"] == 8
    assert status["first_ts"] is not None


def test_import_cpe_mismatch(client, tmp_path) -> None:
    _login(client)
    sp_id = _make_sp(client, identifier="PT000OTHER")
    res = _import_file(client, tmp_path, sp_id, [("2026/07/01", "10:15", "1,0", "Real")])
    assert res.status_code == 422
    res = _import_file(
        client, tmp_path, sp_id, [("2026/07/01", "10:15", "1,0", "Real")], force=True
    )
    assert res.status_code == 200


def test_range_endpoint(client, tmp_path) -> None:
    _login(client)
    sp_id = _make_sp(client)
    _import_file(client, tmp_path, sp_id, [("2026/07/01", "10:15", "2,0", "Real")])
    data = client.get(
        f"/api/consumption/range?supply_point_id={sp_id}"
        "&start=2026-07-01T00:00:00Z&end=2026-07-02T00:00:00Z"
    ).json()
    assert len(data) == 1
    assert data[0]["kwh"] == 0.5
