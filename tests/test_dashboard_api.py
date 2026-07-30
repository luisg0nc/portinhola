def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


def _make_bill(client, doc: str, issue_date: str, lines: list[dict], new_sps: list[dict]):
    return client.post(
        "/api/bills/confirm",
        json={
            "upload_token": None,
            "bill": {
                "issuer_nif": "504435302",
                "doc_number": doc,
                "issue_date": issue_date,
                "total_cents": sum(line["amount_cents"] for line in lines),
                "parse_status": "manual",
            },
            "lines": lines,
            "new_supply_points": new_sps,
        },
    )


def test_costs_grouped_by_month_and_utility(client) -> None:
    _login(client)
    res = _make_bill(
        client,
        "FT A/1",
        "2026-06-09",
        [
            {"description": "energia", "category": "energy", "amount_cents": 3000,
             "contract_id": -1},
            {"description": "potencia", "category": "power", "amount_cents": 400,
             "contract_id": -1},
        ],
        [
            {"utility": "electricity", "identifier": "PT000CPE1", "name": "Casa",
             "contract": {"supplier_name": "G9", "supplier_nif": "504435302",
                          "start_date": "2026-01-01"}}
        ],
    )
    assert res.status_code == 201
    res = _make_bill(
        client,
        "FT A/2",
        "2026-07-09",
        [
            {"description": "agua", "category": "energy", "amount_cents": 1500,
             "contract_id": None}
        ],
        [],
    )
    assert res.status_code == 201

    data = client.get("/api/dashboard/costs?months=13").json()
    months = data["months"]
    assert [m["month"] for m in months] == ["2026-06", "2026-07"]

    june = months[0]["by_utility"]["electricity"]
    assert june["energy"] == 3000
    assert june["power"] == 400
    assert june["total"] == 3400

    july = months[1]["by_utility"]["unknown"]
    assert july["energy"] == 1500


def test_costs_requires_auth(client) -> None:
    assert client.get("/api/dashboard/costs").status_code == 401


def test_live_estimate(client, app) -> None:
    from datetime import UTC, datetime, timedelta

    from portinhola.db.consumption_repo import upsert_intervals

    _login(client)
    sp_id = client.post(
        "/api/supply-points",
        json={"utility": "electricity", "identifier": "PT000EST", "name": "Casa"},
    ).json()["id"]
    client.post(
        f"/api/supply-points/{sp_id}/contracts",
        json={
            "supplier_name": "G9",
            "supplier_nif": "504435302",
            "power_kva": 4.6,
            "cycle": "simples",
            "start_date": "2026-01-01",
        },
    )
    start = datetime.now(UTC) - timedelta(days=10)
    rows = [
        (start + timedelta(minutes=15 * i), 0.1, "file_import", "real")
        for i in range(10 * 96)
    ]
    with app.state.sessionmaker() as db:
        upsert_intervals(db, sp_id, rows)

    res = client.get(f"/api/dashboard/estimate?supply_point_id={sp_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["kwh"] > 0
    assert body["estimated_cents"] > 0
    assert body["period_start"]


def test_costs_totals_include_vat(client) -> None:
    _login(client)
    _make_bill(
        client,
        "FT V/1",
        "2026-05-09",
        [
            {"description": "energia", "category": "energy", "amount_cents": 1000,
             "vat_rate": 23, "contract_id": -1},
        ],
        [
            {"utility": "electricity", "identifier": "PT000VAT", "name": "Casa",
             "contract": {"supplier_name": "G9", "supplier_nif": "504435302",
                          "start_date": "2026-01-01"}}
        ],
    )
    data = client.get("/api/dashboard/costs?months=13").json()
    may = data["months"][0]["by_utility"]["electricity"]
    assert may["energy"] == 1000
    assert may["vat"] == 230
    assert may["total"] == 1230


def test_yearly_totals(client) -> None:
    _login(client)
    _make_bill(
        client,
        "FT Y/1",
        "2025-03-09",
        [
            {"description": "energia", "category": "energy", "amount_cents": 2000,
             "vat_rate": 6, "contract_id": -1},
        ],
        [
            {"utility": "electricity", "identifier": "PT000YR", "name": "Casa",
             "contract": {"supplier_name": "G9", "supplier_nif": "504435302",
                          "start_date": "2025-01-01"}}
        ],
    )
    _make_bill(
        client,
        "FT Y/2",
        "2026-03-09",
        [
            {"description": "energia", "category": "energy", "amount_cents": 3000,
             "vat_rate": 6, "contract_id": 1},
        ],
        [],
    )
    data = client.get("/api/dashboard/yearly").json()
    years = {y["year"]: y["by_utility"] for y in data["years"]}
    assert years["2025"]["electricity"]["total"] == 2120
    assert years["2026"]["electricity"]["total"] == 3180
