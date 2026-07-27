def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


def test_settings_require_auth(client) -> None:
    assert client.get("/api/settings").status_code == 401


def test_default_language_is_pt(client) -> None:
    _login(client)
    res = client.get("/api/settings")
    assert res.status_code == 200
    assert res.json() == {"language": "pt"}


def test_update_language(client) -> None:
    _login(client)
    assert client.put("/api/settings", json={"language": "en"}).status_code == 204
    assert client.get("/api/settings").json() == {"language": "en"}


def test_invalid_language_rejected(client) -> None:
    _login(client)
    assert client.put("/api/settings", json={"language": "fr"}).status_code == 422
