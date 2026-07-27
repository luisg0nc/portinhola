def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


def test_supply_point_crud_and_contract_succession(client) -> None:
    _login(client)
    res = client.post(
        "/api/supply-points",
        json={"utility": "electricity", "identifier": "PT0002000000000001AA", "name": "Casa"},
    )
    assert res.status_code == 201
    sp_id = res.json()["id"]

    assert (
        client.post(
            "/api/supply-points",
            json={"utility": "electricity", "identifier": "PT0002000000000001AA", "name": "Dup"},
        ).status_code
        == 409
    )

    res = client.post(
        f"/api/supply-points/{sp_id}/contracts",
        json={"supplier_name": "Old", "supplier_nif": "111111111", "start_date": "2024-01-01"},
    )
    assert res.status_code == 201
    res = client.post(
        f"/api/supply-points/{sp_id}/contracts",
        json={"supplier_name": "G9", "supplier_nif": "504435302", "start_date": "2025-06-01"},
    )
    assert res.status_code == 201
    listing = client.get("/api/supply-points").json()
    contracts = listing[0]["contracts"]
    old = next(c for c in contracts if c["supplier_name"] == "Old")
    assert old["end_date"] == "2025-05-31"

    new_id = next(c for c in contracts if c["supplier_name"] == "G9")["id"]
    assert (
        client.patch(
            f"/api/supply-points/contracts/{new_id}", json={"tariff_name": "Simples"}
        ).status_code
        == 200
    )
    listing = client.get("/api/supply-points").json()
    updated = next(c for c in listing[0]["contracts"] if c["id"] == new_id)
    assert updated["tariff_name"] == "Simples"


def test_requires_auth(client) -> None:
    assert client.get("/api/supply-points").status_code == 401
