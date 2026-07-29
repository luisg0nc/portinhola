def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


VALID_CURL = (
    "curl 'https://balcaodigital.e-redes.pt/api/consumptions/export"
    "?cpe=PT1&startDate=2026-06-01&endDate=2026-07-01' "
    "-H 'authorization: Bearer a.b.c' -b 'PHPSESSID=s'"
)


def test_status_disconnected(client) -> None:
    _login(client)
    assert client.get("/api/eredes/status").json()["connected"] is False


def test_import_and_status(client) -> None:
    _login(client)
    res = client.post("/api/eredes/import", json={"curl": VALID_CURL})
    assert res.status_code == 200
    status = client.get("/api/eredes/status").json()
    assert status["connected"] is True


def test_import_rejects_wrong_host(client) -> None:
    _login(client)
    bad = "curl 'https://evil.com/api/x?s=2026-06-01&e=2026-07-01'"
    res = client.post("/api/eredes/import", json={"curl": bad})
    assert res.status_code == 422
    assert res.json()["detail"] == "wrong_host"


def test_import_rejects_not_curl(client) -> None:
    _login(client)
    res = client.post("/api/eredes/import", json={"curl": "hello"})
    assert res.status_code == 422
    assert res.json()["detail"] == "not_curl"


def test_disconnect(client) -> None:
    _login(client)
    client.post("/api/eredes/import", json={"curl": VALID_CURL})
    assert client.post("/api/eredes/disconnect").status_code == 204
    assert client.get("/api/eredes/status").json()["connected"] is False


def test_status_requires_auth(client) -> None:
    assert client.get("/api/eredes/status").status_code == 401
