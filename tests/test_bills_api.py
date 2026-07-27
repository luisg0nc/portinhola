from tests.test_pdf import _make_pdf_with_qr

TEST_QR = (
    "A:999999990*B:299999998*C:PT*D:FT*E:N*F:20260701*G:FT T/1*H:AAAA1111-1*"
    "I1:PT*I3:10.00*I4:0.60*N:0.60*O:10.60*Q:xxxx*R:1*"
)


def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


def _upload(client, tmp_path, name: str = "up.pdf"):
    pdf = tmp_path / name
    _make_pdf_with_qr(pdf, TEST_QR)
    with open(pdf, "rb") as fh:
        return client.post(
            "/api/bills/upload", files={"file": (name, fh, "application/pdf")}
        ).json()


def _confirm_payload(draft, atcud: str = "AAAA1111-1"):
    return {
        "upload_token": draft["upload_token"] if draft else None,
        "bill": {
            "issuer_nif": "999999990",
            "doc_number": "FT T/1",
            "atcud": atcud,
            "issue_date": "2026-07-01",
            "total_cents": 1060,
            "parse_status": "partial",
        },
        "lines": [
            {
                "description": "Fornecimento",
                "category": "energy",
                "utility": "water",
                "amount_cents": 1000,
                "vat_rate": 6,
                "contract_id": -1,
            }
        ],
        "new_supply_points": [
            {
                "utility": "water",
                "identifier": "200000",
                "name": "Casa",
                "contract": {
                    "supplier_name": "Be Water",
                    "supplier_nif": "999999990",
                    "start_date": "2026-01-01",
                },
            }
        ],
    }


def test_upload_confirm_roundtrip(client, tmp_path) -> None:
    _login(client)
    draft = _upload(client, tmp_path)
    assert draft["qr"]["doc_number"] == "FT T/1"
    assert draft["extractor"] is None
    assert draft["duplicate_of"] is None

    res = client.post("/api/bills/confirm", json=_confirm_payload(draft))
    assert res.status_code == 201
    bill_id = res.json()["id"]

    detail = client.get(f"/api/bills/{bill_id}").json()
    assert detail["total_cents"] == 1060
    assert detail["pdf_available"] is True
    assert detail["lines"][0]["contract_id"] is not None

    listing = client.get("/api/bills").json()
    assert listing[0]["id"] == bill_id
    assert listing[0]["utilities"] == ["water"]

    assert client.get(f"/api/bills/{bill_id}/pdf").status_code == 200


def test_upload_detects_duplicate(client, tmp_path) -> None:
    _login(client)
    draft = _upload(client, tmp_path)
    client.post("/api/bills/confirm", json=_confirm_payload(draft))
    second = _upload(client, tmp_path, "again.pdf")
    assert second["duplicate_of"] is not None


def test_duplicate_atcud_rejected(client) -> None:
    _login(client)
    payload = {
        "upload_token": None,
        "bill": {
            "issuer_nif": "999999990",
            "doc_number": "FT T/9",
            "atcud": "AAAA1111-9",
            "issue_date": "2026-07-01",
            "total_cents": 1060,
            "parse_status": "manual",
        },
        "lines": [],
        "new_supply_points": [],
    }
    assert client.post("/api/bills/confirm", json=payload).status_code == 201
    assert client.post("/api/bills/confirm", json=payload).status_code == 409


def test_manual_entry_without_pdf(client) -> None:
    _login(client)
    res = client.post(
        "/api/bills/confirm",
        json={
            "upload_token": None,
            "bill": {
                "issuer_nif": "111111111",
                "doc_number": "M/1",
                "issue_date": "2026-05-01",
                "total_cents": 500,
                "parse_status": "manual",
            },
            "lines": [
                {
                    "description": "Água",
                    "category": "energy",
                    "utility": "water",
                    "amount_cents": 500,
                    "contract_id": None,
                }
            ],
            "new_supply_points": [],
        },
    )
    assert res.status_code == 201
    detail = client.get(f"/api/bills/{res.json()['id']}").json()
    assert detail["pdf_available"] is False


def test_delete_bill(client) -> None:
    _login(client)
    res = client.post(
        "/api/bills/confirm",
        json={
            "upload_token": None,
            "bill": {
                "issuer_nif": "111111111",
                "doc_number": "M/2",
                "issue_date": "2026-05-01",
                "total_cents": 100,
                "parse_status": "manual",
            },
            "lines": [],
            "new_supply_points": [],
        },
    )
    bill_id = res.json()["id"]
    assert client.delete(f"/api/bills/{bill_id}").status_code == 204
    assert client.get(f"/api/bills/{bill_id}").status_code == 404


def test_upload_rejects_non_pdf(client, tmp_path) -> None:
    _login(client)
    bad = tmp_path / "x.txt"
    bad.write_text("not a pdf")
    with open(bad, "rb") as fh:
        res = client.post("/api/bills/upload", files={"file": ("x.txt", fh, "text/plain")})
    assert res.status_code == 415
