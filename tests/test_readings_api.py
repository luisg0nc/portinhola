def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


def _make_sp(client, utility: str = "gas", identifier: str = "SP-GAS") -> int:
    res = client.post(
        "/api/supply-points",
        json={"utility": utility, "identifier": identifier, "name": "Casa"},
    )
    return res.json()["id"]


def test_create_and_latest(client) -> None:
    _login(client)
    sp_id = _make_sp(client)
    res = client.post(
        "/api/readings",
        json={"supply_point_id": sp_id, "values": {"Total": 3384.0}},
    )
    assert res.status_code == 201
    latest = client.get(f"/api/readings/latest?supply_point_id={sp_id}").json()
    assert latest["Total"]["value"] == 3384.0


def test_monotonic_rejection_and_override(client) -> None:
    _login(client)
    sp_id = _make_sp(client, identifier="SP-GAS2")
    client.post("/api/readings", json={"supply_point_id": sp_id, "values": {"Total": 100.0}})
    res = client.post(
        "/api/readings", json={"supply_point_id": sp_id, "values": {"Total": 50.0}}
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "value_decreased"
    res = client.post(
        "/api/readings",
        json={"supply_point_id": sp_id, "values": {"Total": 50.0}, "allow_decrease": True},
    )
    assert res.status_code == 201


def test_unknown_register_rejected(client) -> None:
    _login(client)
    sp_id = _make_sp(client, identifier="SP-GAS3")
    res = client.post(
        "/api/readings", json={"supply_point_id": sp_id, "values": {"Ponta": 1.0}}
    )
    assert res.status_code == 422


def test_electricity_multi_register(client) -> None:
    _login(client)
    sp_id = _make_sp(client, utility="electricity", identifier="SP-ELEC")
    res = client.post(
        "/api/readings",
        json={
            "supply_point_id": sp_id,
            "values": {"Vazio": 4900.0, "Cheias": 6307.0, "Ponta": 2799.0},
        },
    )
    assert res.status_code == 201
    assert len(res.json()) == 3


def test_list_mark_submitted_and_delete(client) -> None:
    _login(client)
    sp_id = _make_sp(client, identifier="SP-GAS4")
    res = client.post(
        "/api/readings", json={"supply_point_id": sp_id, "values": {"Total": 10.0}}
    )
    reading_id = res.json()[0]["id"]
    listing = client.get(f"/api/readings?supply_point_id={sp_id}").json()
    assert len(listing) == 1
    assert (
        client.patch(
            f"/api/readings/{reading_id}", json={"submission_status": "submitted_manual"}
        ).status_code
        == 200
    )
    assert (
        client.get(f"/api/readings?supply_point_id={sp_id}").json()[0]["submission_status"]
        == "submitted_manual"
    )
    assert client.delete(f"/api/readings/{reading_id}").status_code == 204
