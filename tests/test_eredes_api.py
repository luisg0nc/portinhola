def _login(client) -> None:
    client.post("/api/auth/setup", json={"password": "hunter2hunter2"})


TOKEN = "eyJhbGciOi.someLongAatTokenValue.signaturePart"


def test_status_disconnected(client) -> None:
    _login(client)
    body = client.get("/api/eredes/status").json()
    assert body["connected"] is False
    assert body["needs_supply_point"] is True
    assert body["last_job"] is None


def test_status_reports_last_sync_job(client, app) -> None:
    """The UI shows the outcome of the last sync — the API must surface the
    job row, with the clean failure code for failed runs."""
    from datetime import UTC, datetime

    from portinhola.db.models import Job

    _login(client)
    with app.state.sessionmaker() as db:
        db.add(
            Job(
                type="eredes_sync",
                status="failed",
                started_at=datetime(2026, 7, 30, 0, 20, tzinfo=UTC),
                finished_at=datetime(2026, 7, 30, 0, 21, tzinfo=UTC),
                log="",
                error="no_supply_point",
            )
        )
        db.commit()
    job = client.get("/api/eredes/status").json()["last_job"]
    assert job["status"] == "failed"
    assert job["message"] == "no_supply_point"
    assert job["finished_at"].startswith("2026-07-30")


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


def test_import_triggers_immediate_sync(client, monkeypatch) -> None:
    """The aat lives ~91 min and can't be renewed server-side, so importing
    must sync right away rather than waiting for a schedule."""
    spawned: list[str] = []
    monkeypatch.setattr(
        "portinhola.api.eredes.spawn_job", lambda job_type: spawned.append(job_type)
    )
    _login(client)
    res = client.post("/api/eredes/import", json={"token": TOKEN})
    assert res.status_code == 200
    assert res.json()["sync_started"] is True
    assert spawned == ["eredes_sync"]
