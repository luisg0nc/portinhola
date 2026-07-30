from datetime import UTC, datetime, timedelta


def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


def _make_elec_sp(client, app) -> int:
    sp_id = client.post(
        "/api/supply-points",
        json={"utility": "electricity", "identifier": "PT000CALC", "name": "Casa"},
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
    return sp_id


def _seed_consumption(
    app, sp_id: int, days: int = 60, kwh_per_day: float = 10.0, start: datetime | None = None
) -> None:
    from portinhola.db.consumption_repo import upsert_intervals

    start = start or datetime(2026, 5, 1, tzinfo=UTC)
    rows = []
    per_slot = kwh_per_day / 96
    for i in range(days * 96):
        rows.append((start + timedelta(minutes=15 * i), per_slot, "file_import", "real"))
    with app.state.sessionmaker() as db:
        upsert_intervals(db, sp_id, rows)


def test_electricity_ranking(client, app) -> None:
    _login(client)
    sp_id = _make_elec_sp(client, app)
    _seed_consumption(app, sp_id)
    res = client.get(f"/api/calculator/electricity?supply_point_id={sp_id}&months=2")
    assert res.status_code == 200
    body = res.json()
    assert body["window"]["kwh"] > 0
    totals = [r["total_cents"] for r in body["results"]]
    assert totals == sorted(totals)
    ids = [r["tariff_id"] for r in body["results"]]
    assert "g9-simples" in ids
    assert body["current"] is not None
    assert body["current"]["tariff_id"] == "g9-simples"
    first = body["results"][0]
    assert first["delta_cents"] <= 0
    assert "breakdown" in first


def test_potencia_recommendation(client, app) -> None:
    _login(client)
    sp_id = _make_elec_sp(client, app)
    _seed_consumption(app, sp_id, days=30, kwh_per_day=5.0)  # peak ~0.21 kW
    res = client.get(f"/api/calculator/potencia?supply_point_id={sp_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["contracted_kva"] == 4.6
    assert body["peak_kw"] < 1.0
    assert body["recommended_kva"] < 4.6
    assert body["saving_cents_year"] is not None
    assert body["saving_cents_year"] > 0


def test_gas_ranking_from_bill_lines(client, app) -> None:
    _login(client)
    res = client.post(
        "/api/bills/confirm",
        json={
            "upload_token": None,
            "bill": {
                "issuer_nif": "504435302",
                "doc_number": "GAS/1",
                "issue_date": "2026-07-09",
                "period_start": "2026-06-09",
                "period_end": "2026-07-08",
                "total_cents": 5000,
                "parse_status": "manual",
            },
            "lines": [
                {
                    "description": "Gás natural - energia",
                    "category": "energy",
                    "utility": "gas",
                    "quantity": 300.0,
                    "unit": "kWh",
                    "period_start": "2026-06-09",
                    "period_end": "2026-07-08",
                    "amount_cents": 3200,
                    "contract_id": -1,
                }
            ],
            "new_supply_points": [
                {
                    "utility": "gas",
                    "identifier": "PT160GAS",
                    "name": "Casa G",
                    "contract": {
                        "supplier_name": "G9",
                        "supplier_nif": "504435302",
                        "gas_tier": 2,
                        "start_date": "2026-01-01",
                    },
                }
            ],
        },
    )
    assert res.status_code == 201
    sp_res = client.get("/api/supply-points").json()
    sp_id = next(sp["id"] for sp in sp_res if sp["utility"] == "gas")
    res = client.get(f"/api/calculator/gas?supply_point_id={sp_id}&months=12")
    assert res.status_code == 200
    body = res.json()
    assert body["window"]["kwh"] == 300.0
    totals = [r["total_cents"] for r in body["results"]]
    assert totals == sorted(totals)
    assert any(r["tariff_id"] == "g9-gas" for r in body["results"])


def test_calibration(client, app) -> None:
    _login(client)
    sp_id = _make_elec_sp(client, app)
    _seed_consumption(
        app, sp_id, days=61, kwh_per_day=295 / 30, start=datetime(2026, 5, 15, tzinfo=UTC)
    )
    res = client.post(
        "/api/bills/confirm",
        json={
            "upload_token": None,
            "bill": {
                "issuer_nif": "504435302",
                "doc_number": "CAL/1",
                "issue_date": "2026-07-09",
                "period_start": "2026-06-09",
                "period_end": "2026-07-08",
                "total_cents": 6719,
                "parse_status": "manual",
            },
            "lines": [
                {
                    "description": "eletricidade total s/IVA",
                    "category": "energy",
                    "utility": "electricity",
                    "amount_cents": 5929,
                    "contract_id": 1,
                }
            ],
            "new_supply_points": [],
        },
    )
    bill_id = res.json()["id"]
    res = client.get(
        f"/api/calculator/calibration?supply_point_id={sp_id}&bill_id={bill_id}"
    )
    assert res.status_code == 200
    body = res.json()
    assert abs(body["delta_cents"]) <= 10


def _make_gas_sp_with_bill(client) -> int:
    sp_id = client.post(
        "/api/supply-points",
        json={"utility": "gas", "identifier": "PT160GAS", "name": "Casa"},
    ).json()["id"]
    client.post(
        f"/api/supply-points/{sp_id}/contracts",
        json={
            "supplier_name": "G9",
            "supplier_nif": "504435302",
            "gas_tier": 2,
            "start_date": "2026-01-01",
        },
    )
    contracts = client.get("/api/supply-points").json()
    contract_id = next(
        c["id"] for sp in contracts if sp["id"] == sp_id for c in sp["contracts"]
    )
    client.post(
        "/api/bills/confirm",
        json={
            "upload_token": None,
            "bill": {
                "issuer_nif": "504435302",
                "doc_number": "FT GAS/1",
                "issue_date": "2026-06-09",
                "period_start": "2026-05-09",
                "period_end": "2026-06-08",
                "total_cents": 5000,
                "parse_status": "manual",
            },
            "lines": [
                {
                    "description": "gás energia",
                    "category": "energy",
                    "quantity": 300.0,
                    "unit": "kWh",
                    "amount_cents": 3200,
                    "vat_rate": 23,
                    "contract_id": contract_id,
                }
            ],
            "new_supply_points": [],
        },
    )
    return sp_id


def test_dual_ranking(client, app) -> None:
    """Dual view: bundle rows (sourced discounts or marked plain sums),
    a best-mixed-pair row, and the current combo as delta baseline."""
    _login(client)
    elec_sp = _make_elec_sp(client, app)
    _seed_consumption(app, elec_sp)
    _make_gas_sp_with_bill(client)

    res = client.get("/api/calculator/dual?months=2")
    assert res.status_code == 200
    body = res.json()
    assert body["window"]["elec_kwh"] > 0
    assert body["window"]["gas_kwh"] == 300.0

    kinds = {row["kind"] for row in body["results"]}
    assert {"bundle", "mixed", "current"} <= kinds

    totals = [row["total_cents"] for row in body["results"]]
    assert totals == sorted(totals)

    current = next(row for row in body["results"] if row["kind"] == "current")
    assert current["delta_cents"] == 0
    assert "G9" in current["supplier"]

    edp = next(row for row in body["results"] if row["name"] == "EDP Luz+Gás")
    # EDP's 15%/5% dual discount is a first-12-months promo: excluded from
    # the steady-state total, pro-rated into the first-year one.
    assert edp["discount_cents"] == 0
    assert edp["first_year_total_cents"] < edp["total_cents"]
    assert edp["no_discount_data"] is False

    plain = [row for row in body["results"] if row["no_discount_data"]]
    assert plain, "suppliers without sourced dual discounts appear as marked sums"
    assert all(row["discount_cents"] == 0 for row in plain)

    mixed = next(row for row in body["results"] if row["kind"] == "mixed")
    best_bundle_total = min(
        row["total_cents"] for row in body["results"] if row["kind"] == "bundle"
    )
    assert mixed["total_cents"] <= best_bundle_total or mixed["discount_cents"] == 0
