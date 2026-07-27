
from portinhola.core.billdata import BillData
from portinhola.reporters.base import Confirmation, Reporter, get_reporter, register

assert BillData  # imported to prove extractor/reporter packages coexist


def test_registry_lookup() -> None:
    @register
    class Dummy(Reporter):
        name = "dummy"
        version = "1"
        supplier_nifs = frozenset({"123456789"})

        def submit(self, readings, contract) -> Confirmation:
            return Confirmation(reference="OK-1")

    reporter = get_reporter("123456789")
    assert reporter is not None
    assert reporter.name == "dummy"
    assert get_reporter("000000000") is None


def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


def test_submit_endpoint_manual_fallback(client) -> None:
    _login(client)
    sp_id = client.post(
        "/api/supply-points",
        json={"utility": "water", "identifier": "SP-W1", "name": "Casa"},
    ).json()["id"]
    contract_id = client.post(
        f"/api/supply-points/{sp_id}/contracts",
        json={
            "supplier_name": "Be Water",
            "supplier_nif": "505084040",
            "start_date": "2026-01-01",
        },
    ).json()["id"]
    client.patch(
        f"/api/supply-points/contracts/{contract_id}",
        json={"submit_phone": "800 205 484", "submit_reference": "0464960186"},
    )
    reading_id = client.post(
        "/api/readings", json={"supply_point_id": sp_id, "values": {"Total": 470.0}}
    ).json()[0]["id"]

    res = client.post("/api/readings/submit", json={"supply_point_id": sp_id})
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "manual"
    assert body["submit_phone"] == "800 205 484"
    assert body["submit_reference"] == "0464960186"

    listing = client.get(f"/api/readings?supply_point_id={sp_id}").json()
    assert listing[0]["submission_status"] == "needs_manual"

    client.patch(f"/api/readings/{reading_id}", json={"submission_status": "submitted_manual"})
    assert (
        client.get(f"/api/readings?supply_point_id={sp_id}").json()[0]["submission_status"]
        == "submitted_manual"
    )
