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
