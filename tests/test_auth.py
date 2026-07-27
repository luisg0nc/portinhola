def test_status_before_setup(client) -> None:
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    assert res.json() == {"setup_required": True, "authenticated": False}


def test_setup_sets_password_and_logs_in(client) -> None:
    res = client.post("/api/auth/setup", json={"password": "hunter2hunter2"})
    assert res.status_code == 204
    assert "portinhola_session" in res.cookies
    status = client.get("/api/auth/status").json()
    assert status == {"setup_required": False, "authenticated": True}


def test_setup_rejected_when_already_configured(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})
    res = client.post("/api/auth/setup", json={"password": "another-password"})
    assert res.status_code == 409


def test_setup_rejects_short_password(client) -> None:
    res = client.post("/api/auth/setup", json={"password": "short"})
    assert res.status_code == 422


def test_login_success_and_failure(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"password": "wrong-password"}).status_code == 401
    res = client.post("/api/auth/login", json={"password": "hunter2hunter2"})
    assert res.status_code == 204
    assert client.get("/api/auth/status").json()["authenticated"] is True


def test_login_rate_limited_after_five_failures(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})
    client.cookies.clear()
    for _ in range(5):
        client.post("/api/auth/login", json={"password": "wrong-password"})
    res = client.post("/api/auth/login", json={"password": "hunter2hunter2"})
    assert res.status_code == 429


def test_logout_clears_session(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/status").json()["authenticated"] is False


def test_change_password(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})
    res = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong", "new_password": "new-password-1"},
    )
    assert res.status_code == 401
    res = client.post(
        "/api/auth/change-password",
        json={"current_password": "hunter2hunter2", "new_password": "new-password-1"},
    )
    assert res.status_code == 204
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"password": "new-password-1"}).status_code == 204
