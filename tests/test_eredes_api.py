def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


TOKEN = "eyJhbGciOi.someLongAatTokenValue.signaturePart"


def test_status_disconnected(client) -> None:
    _login(client)
    assert client.get("/api/eredes/status").json()["connected"] is False


def test_import_and_status(client) -> None:
    _login(client)
    res = client.post("/api/eredes/import", json={"token": TOKEN})
    assert res.status_code == 200
    assert client.get("/api/eredes/status").json()["connected"] is True


def test_import_rejects_empty(client) -> None:
    _login(client)
    assert client.post("/api/eredes/import", json={"token": "   "}).status_code == 422


def test_import_rejects_cookie_string(client) -> None:
    # Users must paste the bare aat VALUE, not a "name=value" pair.
    _login(client)
    res = client.post("/api/eredes/import", json={"token": "aat=abc"})
    assert res.status_code == 422
    assert res.json()["detail"] == "invalid_token"


def test_disconnect(client) -> None:
    _login(client)
    client.post("/api/eredes/import", json={"token": TOKEN})
    assert client.post("/api/eredes/disconnect").status_code == 204
    assert client.get("/api/eredes/status").json()["connected"] is False


def test_status_requires_auth(client) -> None:
    assert client.get("/api/eredes/status").status_code == 401
